import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from PIL import Image, ImageFilter

from app.models.enums import BackgroundIsolationStatus, PresentationType

logger = logging.getLogger(__name__)

# Milestone 6's refinement step turns an M4 crop into a catalog-ready
# image. Tier 1 (canvas/padding/centering/resize/sharpen) below is plain
# Pillow processing -- deterministic, pixel-preserving except for the
# padding border it adds, and runs for every product. It is high-quality
# RESIZING, not true AI super-resolution/upscaling -- see the module docs
# and README for that distinction; nothing here invents detail that wasn't
# already in the source crop.
#
# Tier 2 (background isolation) delegates to a BackgroundRemover
# implementation -- kept as a narrow Protocol, mirroring AIProductAnalyzer
# in app.services.ai.types, so the concrete choice (rembg today) never
# leaks into this module's own logic or its tests. Isolation is now
# attempted for every "suitable" presentation, including bulk/loose
# products (not just packaged/jar/bottle) -- the goal is the same clean,
# isolated-on-white catalog look for a natural pile of loose nuts/mix as
# for a packaged item. Because segmenting a loose/bulk pile from its
# tray/bin is materially harder and riskier than segmenting one packaged
# object, every isolation attempt (regardless of presentation) is run
# through _is_isolation_usable below before being trusted -- an attempt
# that clearly destroyed too much of the real product is rejected and
# this falls back to Tier-1-only output. This is image ISOLATION, never
# generative recreation: nothing here can add, remove, rearrange, or
# invent product content -- it can only keep or discard pixels that were
# already in the source crop.

CANVAS_SIZE = 1200
PADDING_RATIO = 0.08  # ~8% margin on each side of the padded product box
BACKGROUND_COLOR = (255, 255, 255)
JPEG_QUALITY = 92
UNSHARP_RADIUS = 1.5
UNSHARP_PERCENT = 60
UNSHARP_THRESHOLD = 3

# Presentations "suitable" for background isolation -- every known,
# confidently-classified presentation. Deliberately excludes OTHER/None:
# an unclassified presentation gives no basis for judging whether
# isolation is even appropriate, so those stay Tier-1-only (their real,
# honest background is kept) rather than risk running a fundamentally
# uncertain operation on an unknown scene.
BACKGROUND_ISOLATION_PRESENTATIONS = frozenset(
    {
        PresentationType.PACKAGED,
        PresentationType.JAR,
        PresentationType.BOTTLE,
        PresentationType.BULK_TRAY,
        PresentationType.BULK_LOOSE,
    }
)

# Fraction of the ORIGINAL crop's pixel area that an isolation result must
# still retain (alpha above a small noise floor) to be trusted. This is a
# deterministic, purely quantitative safety net -- not a quality/aesthetic
# judgment -- against a segmentation pass that over-aggressively erased
# real product (a known risk on textured loose/bulk piles). Chosen
# conservatively: a legitimate isolation (even one that removes a lot of
# tray/shelf/shadow) should comfortably retain far more than this; a
# result below it is far more likely to be a failed segmentation than a
# real, honest product that happens to be small.
MIN_RETAINED_AREA_RATIO = 0.15
# Alpha values at/below this are treated as "background", not product --
# skips near-zero anti-aliasing noise around a mask edge rather than
# counting it as retained product area.
_ALPHA_NOISE_FLOOR = 16


class BackgroundRemover(Protocol):
    """Narrow interface for Tier 2 background isolation. `remove` takes
    encoded source image bytes and returns encoded RGBA image bytes (the
    isolated subject on a transparent background) -- provider-agnostic by
    construction, the same way AIProductAnalyzer is."""

    def remove(self, image_bytes: bytes) -> bytes: ...


@dataclass(frozen=True)
class RefinementResult:
    image_bytes: bytes  # final encoded JPEG
    background_isolation_status: BackgroundIsolationStatus


def refine_product_image(
    crop_bytes: bytes,
    presentation: PresentationType | None,
    background_remover: BackgroundRemover | None,
) -> RefinementResult:
    """Run Milestone 6 refinement on one already-cropped product image.

    Tier 1 always runs. Tier 2 (background isolation) is attempted when
    both `background_remover` is provided AND `presentation` is one of
    BACKGROUND_ISOLATION_PRESENTATIONS -- now every confidently-classified
    presentation, including bulk/loose products (see module docstring).

    Every isolation attempt is validated by _is_isolation_usable before
    being trusted: a result the background remover raised on, returned
    something Pillow can't decode, or that clearly destroyed too much of
    the original product (see MIN_RETAINED_AREA_RATIO) is REJECTED and
    this falls back to Tier-1-only output -- background isolation can only
    ever be an enhancement, never something that makes a product's refined
    image worse, and never something that fabricates missing product to
    compensate. Only a failure to even decode `crop_bytes` itself (a
    genuinely corrupt/unreadable crop) propagates to the caller, since
    there is nothing safe to fall back to in that case.
    """
    with Image.open(BytesIO(crop_bytes)) as original:
        original.load()
        working = original.convert("RGBA")
        original_size = original.size

    isolation_status = BackgroundIsolationStatus.NOT_ATTEMPTED
    if background_remover is not None and presentation in BACKGROUND_ISOLATION_PRESENTATIONS:
        try:
            isolated_bytes = background_remover.remove(crop_bytes)
            with Image.open(BytesIO(isolated_bytes)) as isolated_raw:
                isolated_raw.load()
                isolated = isolated_raw.convert("RGBA")

            if _is_isolation_usable(original_size, isolated):
                working = isolated
                isolation_status = BackgroundIsolationStatus.APPLIED
            else:
                logger.warning(
                    "Background isolation retained too little of the product "
                    "(presentation=%s); rejecting and falling back to Tier 1 only.",
                    presentation,
                )
                isolation_status = BackgroundIsolationStatus.REJECTED
                # `working` is still the original crop from above -- never
                # left partially modified by a rejected isolation attempt.
        except Exception:
            logger.warning(
                "Background isolation failed; falling back to Tier 1 only.", exc_info=True
            )
            isolation_status = BackgroundIsolationStatus.REJECTED

    canvas = compose_on_canvas(working)
    canvas = canvas.filter(
        ImageFilter.UnsharpMask(radius=UNSHARP_RADIUS, percent=UNSHARP_PERCENT, threshold=UNSHARP_THRESHOLD)
    )

    buffer = BytesIO()
    canvas.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return RefinementResult(image_bytes=buffer.getvalue(), background_isolation_status=isolation_status)


def _is_isolation_usable(original_size: tuple[int, int], isolated: Image.Image) -> bool:
    """Deterministic, purely quantitative guard against a segmentation
    pass that over-aggressively erased real product -- see
    MIN_RETAINED_AREA_RATIO. Never a generative/AI judgment: only counts
    pixels that are already there."""
    if isolated.mode != "RGBA":
        return False
    bbox = isolated.getchannel("A").getbbox()
    if bbox is None:
        return False  # fully transparent -- isolation erased everything
    return _retained_area_ratio(original_size, isolated) >= MIN_RETAINED_AREA_RATIO


def _retained_area_ratio(original_size: tuple[int, int], isolated: Image.Image) -> float:
    """Fraction of the ORIGINAL crop's pixel area that `isolated` still
    considers part of the product (alpha above _ALPHA_NOISE_FLOOR). rembg
    (and any BackgroundRemover) is expected to preserve the source image's
    dimensions, so this compares like-for-like without any rescaling."""
    original_area = original_size[0] * original_size[1]
    if original_area <= 0:
        return 0.0
    histogram = isolated.getchannel("A").histogram()
    retained_pixels = sum(histogram[_ALPHA_NOISE_FLOOR + 1 :])
    return retained_pixels / original_area


def _trim_transparent_margin(image: Image.Image) -> Image.Image:
    """Crop to the bounding box of the non-transparent silhouette so
    padding is computed against the actual product, not against whatever
    canvas size the background remover happened to return. A no-op for a
    Tier-1-only (fully opaque) crop, since its alpha bbox is the full
    image."""
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    return image.crop(bbox)


def _resize_to_fit(image: Image.Image, max_side: int) -> Image.Image:
    """Scale `image` (preserving aspect ratio, never stretching) so its
    longer side is exactly `max_side` -- scales down a large crop and UP a
    small one with the same LANCZOS resample either way. This is where
    "upscaling when needed" happens: plain high-quality resizing, not a
    generative super-resolution model."""
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    scale = max_side / max(width, height)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.LANCZOS)


def compose_on_canvas(image: Image.Image) -> Image.Image:
    """Center `image` on a fixed CANVAS_SIZE x CANVAS_SIZE, solid
    BACKGROUND_COLOR canvas with consistent padding on every side. Uses
    the image's own alpha channel as a paste mask so an isolated (Tier 2)
    subject's removed background is replaced by the clean canvas color,
    while a Tier-1-only (fully opaque) image simply covers its full box."""
    trimmed = _trim_transparent_margin(image)
    usable_side = round(CANVAS_SIZE * (1 - 2 * PADDING_RATIO))
    fitted = _resize_to_fit(trimmed, usable_side)

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BACKGROUND_COLOR)
    x = (CANVAS_SIZE - fitted.width) // 2
    y = (CANVAS_SIZE - fitted.height) // 2
    if fitted.mode == "RGBA":
        canvas.paste(fitted, (x, y), mask=fitted)
    else:
        canvas.paste(fitted.convert("RGB"), (x, y))
    return canvas


class RembgBackgroundRemover:
    """BackgroundRemover implementation backed by rembg's u2netp model
    (ONNX, CPU, ~4.7MB download, cached locally by rembg itself on first
    use) -- entirely local and free, no network call at inference time
    beyond that one-time model fetch. `rembg`/`onnxruntime` are imported
    lazily (inside __init__/remove, not at module scope) so simply
    importing this module -- as every test does, transitively -- never
    pulls in rembg's own heavier dependencies (opencv-python-headless,
    scikit-image) unless this class is actually instantiated, which tests
    never do (see api/digitizer.get_background_remover)."""

    def __init__(self, model_name: str = "u2netp") -> None:
        from rembg import new_session

        self._session = new_session(model_name)

    def remove(self, image_bytes: bytes) -> bytes:
        from rembg import remove

        return remove(image_bytes, session=self._session)


# --- ProductImageRefiner: the broader Milestone 6 interface -------------
#
# BackgroundRemover/RembgBackgroundRemover above are narrow (background
# isolation only) and remain exactly as they were. ProductImageRefiner is
# one level up: the WHOLE refinement step (local Tier1+Tier2, or an
# approved AI image-editing model), selected once in api/digitizer.py and
# used identically by the orchestration layer regardless of which
# implementation is active -- mirrors AIProductAnalyzer (Milestone 4).


@dataclass(frozen=True)
class RefinementProductContext:
    """Non-sensitive product metadata that may help a refiner understand
    what it's looking at. Deliberately excludes price, barcode, and every
    internal ID -- an image refiner has no legitimate need to see them,
    and price must never be something an AI image model could see, invent,
    or alter."""

    name_en: str | None = None
    name_ar: str | None = None
    category: str | None = None
    selling_mode: str | None = None
    brand: str | None = None
    flavor_variant: str | None = None


@dataclass(frozen=True)
class RefinementRequest:
    crop_bytes: bytes
    presentation: PresentationType | None
    context: RefinementProductContext
    reference_images: list[bytes]


class ProductImageRefiner(Protocol):
    """Interface every Milestone 6 image-refinement implementation must
    satisfy -- narrow and provider-agnostic by construction, the same way
    AIProductAnalyzer (Milestone 4) is. Lets the concrete choice (local
    Tier1+rembg, or an approved AI image-editing model) be swapped without
    touching the orchestration layer or the API."""

    def refine(self, request: RefinementRequest) -> RefinementResult: ...


class LocalBackgroundRefiner:
    """ProductImageRefiner implementation backed entirely by local,
    deterministic processing (Tier 1 Pillow composition + optional Tier 2
    rembg isolation) -- see refine_product_image. Free, always available,
    no network call. Ignores `context` and `reference_images` -- it has no
    use for product metadata or style references, only the crop itself
    and its presentation.

    Used when no AI image-editing model is configured (no
    OPENROUTER_API_KEY) -- a CONFIGURATION fallback, not a runtime one:
    once the AI refiner is configured, a failed AI call is reported as a
    failed refinement, never silently downgraded to this local result (see
    digitizer_refinement_service.refine_digitized_product). This class is
    never deleted or bypassed by the AI path existing -- it remains the
    real implementation used whenever AI isn't configured.
    """

    def __init__(self, background_remover: BackgroundRemover | None) -> None:
        self._background_remover = background_remover

    def refine(self, request: RefinementRequest) -> RefinementResult:
        return refine_product_image(request.crop_bytes, request.presentation, self._background_remover)
