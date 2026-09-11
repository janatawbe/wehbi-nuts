import base64
import logging
from io import BytesIO
from typing import Any

import httpx
from PIL import Image, ImageFilter

from app.services.ai.image_refinement_prompt import build_prompt_text
from app.services.image_refinement_service import (
    JPEG_QUALITY,
    UNSHARP_PERCENT,
    UNSHARP_RADIUS,
    UNSHARP_THRESHOLD,
    RefinementRequest,
    RefinementResult,
    compose_on_canvas,
)
from app.models.enums import BackgroundIsolationStatus

logger = logging.getLogger(__name__)

# Milestone 6's AI image-editing refiner: turns an M4 crop into a
# generatively-recomposed catalog photograph (a natural standalone pile
# for loose/bulk products, an isolated package for packaged/jar/bottle),
# using OpenRouter's dedicated Images API -- NOT the Chat Completions
# endpoint app.services.ai.openrouter_vision_digitizer/enrichment_service
# use for M4/M5's TEXT analysis. Approved for real use on
# "google/gemini-2.5-flash-image" ("Nano Banana") -- a PAID, billed-per-
# image model; see README for the cost/approval trail. Uses the SAME
# OPENROUTER_API_KEY as M4/M5 -- this is a different endpoint/model on the
# same OpenRouter account, not a different provider or credential.

IMAGES_ENDPOINT = "https://openrouter.ai/api/v1/images"
_TIMEOUT_SECONDS = 60.0
# OpenRouter's declared limit for google/gemini-2.5-flash-image is 3 total
# input_references. The primary M4 crop always occupies one of those three
# slots, so at most 2 style references (see reference_images.py's own,
# independently-configured MAX_REFERENCE_IMAGES) are ever appended -- this
# is a hard, defensive cap on top of that, never relied on alone.
MAX_TOTAL_IMAGES = 3


class AIImageRefinementError(Exception):
    """Raised when the AI image-editing request fails outright, or
    succeeds at the HTTP level but returns nothing usable (no image, or
    something Pillow can't decode). Caught by
    digitizer_refinement_service.refine_digitized_product and turned into
    image_refinement_status=FAILED -- NEVER silently downgraded to the
    local rembg result; when the AI refiner is configured and active, a
    failed attempt is a failed refinement, not a quiet substitution (see
    LocalBackgroundRefiner's own docstring)."""


def _to_data_url(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as image:
        fmt = (image.format or "JPEG").lower()
    mime = {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(
        fmt, "image/jpeg"
    )
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _decode_returned_image(body: dict[str, Any]) -> bytes | None:
    """Extracts and validates the first generated image from an OpenRouter
    Images API response (`data: [{"b64_json": ..., "media_type": ...}]`).
    Returns None (never raises) for anything malformed/empty/undecodable
    -- the caller treats that identically to a hard failure."""
    data = body.get("data")
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if not isinstance(first, dict):
        return None
    b64 = first.get("b64_json")
    if not b64 or not isinstance(b64, str):
        return None
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:
        return None
    if not raw:
        return None
    try:
        with Image.open(BytesIO(raw)) as probe:
            probe.verify()
    except Exception:
        return None
    return raw


def _log_usage(model_name: str, usage: dict[str, Any]) -> None:
    """Logs only the small, non-sensitive usage/cost summary OpenRouter
    returns -- never the request/response body (which embeds base64 image
    data), never the API key, never an Authorization header."""
    logger.info(
        "AI image refinement usage: model=%s cost_usd=%s total_tokens=%s",
        model_name,
        usage.get("cost"),
        usage.get("total_tokens"),
    )


class AIProductImageRefiner:
    """ProductImageRefiner implementation backed by OpenRouter's Images
    API. Exactly ONE HTTP attempt per `refine()` call -- no internal
    retry loop, no fallback to a different/cheaper paid model (unlike
    M4/M5's analyzers, which retry transient errors; this endpoint is
    billed per call regardless of outcome, so a manual "Refine" click may
    cost at most one paid attempt). The caller
    (digitizer_refinement_service) is responsible for the one-manual-
    click-equals-one-attempt guarantee by simply never calling this twice
    within one refine() invocation.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        # Injectable for tests (httpx.MockTransport) -- production DI
        # wiring never passes one, so a real httpx.Client is constructed
        # only outside the test suite.
        self._client = http_client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def build_request_payload(self, request: RefinementRequest) -> dict[str, Any]:
        """Pure, network-free: builds the exact request body this refiner
        sends. Image 1 is always `request.crop_bytes` (the real M4 crop,
        source of truth); any reference images follow, capped at
        MAX_TOTAL_IMAGES total. Never includes price or any field beyond
        what build_prompt_text/RefinementProductContext already exclude.
        """
        images = [request.crop_bytes, *request.reference_images][:MAX_TOTAL_IMAGES]
        return {
            "model": self._model_name,
            "prompt": build_prompt_text(request.context, request.presentation),
            "input_references": [
                {"type": "image_url", "image_url": {"url": _to_data_url(image_bytes)}}
                for image_bytes in images
            ],
            "aspect_ratio": "1:1",
        }

    def refine(self, request: RefinementRequest) -> RefinementResult:
        payload = self.build_request_payload(request)

        try:
            response = self._client.post(
                IMAGES_ENDPOINT,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            # exc_info deliberately omitted: an httpx exception can carry
            # the outgoing request (including the Authorization header) --
            # never let that reach the logs. No retry: exactly one paid
            # attempt per call, by design.
            logger.warning("AI image refinement request failed (model=%s).", self._model_name)
            raise AIImageRefinementError("The AI image refinement request failed.") from exc

        usage = body.get("usage")
        if isinstance(usage, dict):
            _log_usage(self._model_name, usage)

        raw_image = _decode_returned_image(body)
        if raw_image is None:
            raise AIImageRefinementError(
                "The AI image refinement service did not return a usable image."
            )

        with Image.open(BytesIO(raw_image)) as decoded:
            decoded.load()
            working = decoded.convert("RGBA")

        # Always re-normalized through the same deterministic canvas step
        # as the local refiner -- guarantees exactly 1200x1200 regardless
        # of whatever square-ish size the model actually returned, without
        # trusting the model's own framing claim.
        canvas = compose_on_canvas(working)
        canvas = canvas.filter(
            ImageFilter.UnsharpMask(
                radius=UNSHARP_RADIUS, percent=UNSHARP_PERCENT, threshold=UNSHARP_THRESHOLD
            )
        )
        buffer = BytesIO()
        canvas.save(buffer, format="JPEG", quality=JPEG_QUALITY)

        return RefinementResult(
            image_bytes=buffer.getvalue(),
            background_isolation_status=BackgroundIsolationStatus.APPLIED,
        )
