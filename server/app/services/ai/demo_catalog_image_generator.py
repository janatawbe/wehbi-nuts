"""DEVELOPMENT/DEMO-ONLY: generates a catalog image for a `WN-DEMO-*`
product from TEXT ALONE, via OpenRouter's Images API -- the SAME endpoint,
model, and account/API key as Milestone 6's real image-EDITING refiner
(app.services.ai.image_editing_refiner.AIProductImageRefiner), just used in
its text-to-image mode instead: no `input_references` key is sent at all,
which OpenRouter's Images API documents as optional (a request with a
prompt only generates from scratch; see the module docstring in
app.services.ai.demo_catalog_image_prompt for why no source photo exists
for these products).

The real Digitizer workflow (real shop photo -> detection/crop -> AI
refinement -> review) is completely untouched by this module -- nothing
here is imported by, or imports from, app.api.digitizer or
app.services.digitizer_refinement_service.
"""
import base64
import logging
from io import BytesIO
from typing import Any

import httpx
from PIL import Image, ImageFilter

from app.services.ai.demo_catalog_image_prompt import DemoProductImageContext, build_prompt_text
from app.services.image_refinement_service import (
    JPEG_QUALITY,
    UNSHARP_PERCENT,
    UNSHARP_RADIUS,
    UNSHARP_THRESHOLD,
    compose_on_canvas,
)

logger = logging.getLogger(__name__)

IMAGES_ENDPOINT = "https://openrouter.ai/api/v1/images"
_TIMEOUT_SECONDS = 60.0


class AIDemoImageGenerationError(Exception):
    """Raised when the generation request fails outright, or succeeds at
    the HTTP level but returns nothing usable (no image, or something
    Pillow can't decode). Never retried -- exactly one paid attempt per
    `generate()` call, mirroring AIProductImageRefiner."""


def _decode_returned_image(body: dict[str, Any]) -> bytes | None:
    """Extracts and validates the first generated image from an OpenRouter
    Images API response (`data: [{"b64_json": ..., "media_type": ...}]`).
    Returns None (never raises) for anything malformed/empty/undecodable."""
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
    returns -- never the request/response body, never the API key."""
    logger.info(
        "AI demo catalog image generation usage: model=%s cost_usd=%s total_tokens=%s",
        model_name,
        usage.get("cost"),
        usage.get("total_tokens"),
    )


class AIDemoCatalogImageGenerator:
    """Text-to-image generator for demo product catalog images. Exactly
    ONE HTTP attempt per `generate()` call -- no retry loop, no fallback
    model. There is no local/free fallback for this (unlike M6's
    LocalBackgroundRefiner): generating a photograph from text alone has
    no non-AI equivalent, so this is only ever invoked when
    OPENROUTER_API_KEY is configured, by explicit developer action (see
    app.scripts.generate_demo_product_images), never automatically.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        # Injectable for tests (httpx.MockTransport) -- production wiring
        # never passes one, so a real httpx.Client is constructed only
        # outside the test suite.
        self._client = http_client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def build_request_payload(self, context: DemoProductImageContext) -> dict[str, Any]:
        """Pure, network-free: builds the exact request body this
        generator sends. Deliberately has NO `input_references` key --
        this is pure text-to-image generation, not image editing."""
        return {
            "model": self._model_name,
            "prompt": build_prompt_text(context),
            "aspect_ratio": "1:1",
        }

    def generate(self, context: DemoProductImageContext) -> bytes:
        payload = self.build_request_payload(context)

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
            # the outgoing request (including the Authorization header).
            logger.warning("AI demo image generation request failed (model=%s).", self._model_name)
            raise AIDemoImageGenerationError("The AI demo image generation request failed.") from exc

        usage = body.get("usage")
        if isinstance(usage, dict):
            _log_usage(self._model_name, usage)

        raw_image = _decode_returned_image(body)
        if raw_image is None:
            raise AIDemoImageGenerationError(
                "The AI demo image generation service did not return a usable image."
            )

        with Image.open(BytesIO(raw_image)) as decoded:
            decoded.load()
            working = decoded.convert("RGBA")

        # Same deterministic canvas/sharpen step as the real Digitizer's
        # refined images, so generated demo images are visually
        # indistinguishable in style from real refined catalog images.
        canvas = compose_on_canvas(working)
        canvas = canvas.filter(
            ImageFilter.UnsharpMask(radius=UNSHARP_RADIUS, percent=UNSHARP_PERCENT, threshold=UNSHARP_THRESHOLD)
        )
        buffer = BytesIO()
        canvas.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        return buffer.getvalue()
