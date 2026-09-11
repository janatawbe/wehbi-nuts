"""Unit tests for the Milestone 6 Tier 1 (Pillow) + Tier 2 (background
isolation) refinement pipeline. The real `rembg`/`onnxruntime` model is
NEVER invoked here -- `BackgroundRemover` is a narrow Protocol, and every
test that needs one uses a scripted fake, never RembgBackgroundRemover."""
from io import BytesIO

import pytest
from PIL import Image

from app.models.enums import BackgroundIsolationStatus, PresentationType
from app.services.image_refinement_service import (
    BACKGROUND_ISOLATION_PRESENTATIONS,
    CANVAS_SIZE,
    MIN_RETAINED_AREA_RATIO,
    refine_product_image,
)


def make_crop_bytes(width: int, height: int, color=(120, 60, 10)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=color).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


class FakeBackgroundRemover:
    """Returns an RGBA image with a transparent margin AROUND the fully
    preserved subject (padding added, nothing erased) -- simulates a
    clean, successful isolation without ever touching rembg. Retains 100%
    of the original subject's pixels, so this always clears
    MIN_RETAINED_AREA_RATIO."""

    def __init__(self) -> None:
        self.calls: list[bytes] = []

    def remove(self, image_bytes: bytes) -> bytes:
        self.calls.append(image_bytes)
        with Image.open(BytesIO(image_bytes)) as source:
            subject = source.convert("RGBA")
        canvas = Image.new("RGBA", (subject.width + 80, subject.height + 80), (0, 0, 0, 0))
        canvas.paste(subject, (40, 40))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()


class PartialBackgroundRemover:
    """Retains roughly half of the original crop's area -- exercises the
    "still usable" side of MIN_RETAINED_AREA_RATIO."""

    def remove(self, image_bytes: bytes) -> bytes:
        with Image.open(BytesIO(image_bytes)) as source:
            width, height = source.size
            rgba = source.convert("RGBA")
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        top_half = rgba.crop((0, 0, width, height // 2))
        canvas.paste(top_half, (0, 0))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()


class DestructiveBackgroundRemover:
    """Simulates a segmentation pass that over-aggressively erased almost
    all of the real product -- correct dimensions, but only a tiny
    fully-opaque speck survives, well below MIN_RETAINED_AREA_RATIO. This
    is the case the safety check exists to catch."""

    def __init__(self) -> None:
        self.calls = 0

    def remove(self, image_bytes: bytes) -> bytes:
        self.calls += 1
        with Image.open(BytesIO(image_bytes)) as source:
            width, height = source.size
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        speck_side = max(1, min(width, height) // 20)
        speck = Image.new("RGBA", (speck_side, speck_side), (120, 60, 10, 255))
        canvas.paste(speck, (0, 0))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()


class FullyErasingBackgroundRemover:
    """Returns a fully transparent image -- the most extreme destructive
    case (isolation erased the entire product)."""

    def remove(self, image_bytes: bytes) -> bytes:
        with Image.open(BytesIO(image_bytes)) as source:
            width, height = source.size
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()


class FailingBackgroundRemover:
    def __init__(self) -> None:
        self.calls = 0

    def remove(self, image_bytes: bytes) -> bytes:
        self.calls += 1
        raise RuntimeError("simulated background-isolation failure")


class UndecodableBackgroundRemover:
    """Returns bytes that are not a valid image at all -- exercises the
    "Pillow can't decode what came back" branch of the fallback, distinct
    from the remover raising outright."""

    def remove(self, image_bytes: bytes) -> bytes:
        return b"not-an-image"


# --- Tier 1: always runs, output shape ----------------------------------


@pytest.mark.parametrize(
    "width,height",
    [(400, 400), (300, 900), (1600, 500), (50, 50), (2000, 2000)],
)
def test_output_canvas_is_always_the_configured_square_size(width, height):
    crop_bytes = make_crop_bytes(width, height)

    result = refine_product_image(crop_bytes, PresentationType.OTHER, None)

    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)
    assert out.format == "JPEG"


def test_tall_narrow_crop_is_not_stretched():
    """A 1:3 aspect-ratio crop must keep that ratio inside the padded box
    -- never be squashed/stretched to fill a square."""
    crop_bytes = make_crop_bytes(300, 900)

    result = refine_product_image(crop_bytes, PresentationType.OTHER, None)

    out = Image.open(BytesIO(result.image_bytes)).convert("RGB")
    # Find the bounding box of the non-background pixels to recover the
    # actual placed product size.
    diff_mask = Image.new("L", out.size)
    out_pixels = out.load()
    mask_pixels = diff_mask.load()
    for x in range(out.width):
        for y in range(out.height):
            mask_pixels[x, y] = 0 if out_pixels[x, y] == (255, 255, 255) else 255
    bbox = diff_mask.getbbox()
    assert bbox is not None
    placed_width = bbox[2] - bbox[0]
    placed_height = bbox[3] - bbox[1]
    # original ratio 300/900 = 0.333...
    assert placed_height > 0
    ratio = placed_width / placed_height
    assert 0.30 <= ratio <= 0.37


def test_small_crop_is_upscaled_to_fill_the_padded_box():
    crop_bytes = make_crop_bytes(50, 50)

    result = refine_product_image(crop_bytes, PresentationType.OTHER, None)

    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)  # still fits the fixed canvas, not left tiny


def test_large_crop_is_downscaled_to_fit_the_padded_box():
    crop_bytes = make_crop_bytes(2000, 2000)

    result = refine_product_image(crop_bytes, PresentationType.OTHER, None)

    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)


def test_corrupt_crop_bytes_raise_instead_of_silently_producing_garbage():
    with pytest.raises(Exception):
        refine_product_image(b"not-a-real-image", PresentationType.PACKAGED, None)


# --- Tier 2 gating: every suitable presentation, including bulk/loose ----


def test_background_isolation_presentations_include_bulk_and_loose():
    assert BACKGROUND_ISOLATION_PRESENTATIONS == {
        PresentationType.PACKAGED,
        PresentationType.JAR,
        PresentationType.BOTTLE,
        PresentationType.BULK_TRAY,
        PresentationType.BULK_LOOSE,
    }


@pytest.mark.parametrize(
    "presentation",
    [
        PresentationType.PACKAGED,
        PresentationType.JAR,
        PresentationType.BOTTLE,
        PresentationType.BULK_TRAY,
        PresentationType.BULK_LOOSE,
    ],
)
def test_background_isolation_is_attempted_for_every_suitable_presentation(presentation):
    remover = FakeBackgroundRemover()
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, presentation, remover)

    assert len(remover.calls) == 1
    assert result.background_isolation_status == BackgroundIsolationStatus.APPLIED


@pytest.mark.parametrize("presentation", [PresentationType.OTHER, None])
def test_background_isolation_never_attempted_for_uncertain_presentations(presentation):
    remover = FakeBackgroundRemover()
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, presentation, remover)

    assert len(remover.calls) == 0
    assert result.background_isolation_status == BackgroundIsolationStatus.NOT_ATTEMPTED


def test_no_background_remover_provided_means_tier1_only_even_for_packaged():
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, PresentationType.PACKAGED, None)

    assert result.background_isolation_status == BackgroundIsolationStatus.NOT_ATTEMPTED
    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)


# --- Tier 2 failure/rejection safety, for BOTH packaged and bulk items ----


@pytest.mark.parametrize(
    "presentation", [PresentationType.BOTTLE, PresentationType.BULK_TRAY, PresentationType.BULK_LOOSE]
)
def test_background_isolation_raising_falls_back_to_tier1_without_raising(presentation):
    remover = FailingBackgroundRemover()
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, presentation, remover)

    assert remover.calls == 1
    assert result.background_isolation_status == BackgroundIsolationStatus.REJECTED
    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)


def test_background_isolation_returning_undecodable_bytes_falls_back_to_tier1():
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, PresentationType.JAR, UndecodableBackgroundRemover())

    assert result.background_isolation_status == BackgroundIsolationStatus.REJECTED
    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)


def test_successful_isolation_produces_a_usable_refined_image():
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, PresentationType.PACKAGED, FakeBackgroundRemover())

    out = Image.open(BytesIO(result.image_bytes))
    out.load()  # would raise if the JPEG bytes were malformed
    assert out.mode == "RGB"
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)


# --- The new safety net: reject a destructive isolation, for bulk items --
# specifically (the case this correction is about), and confirm the
# boundary behavior of MIN_RETAINED_AREA_RATIO. ---------------------------


@pytest.mark.parametrize("presentation", [PresentationType.BULK_TRAY, PresentationType.BULK_LOOSE])
def test_destructive_isolation_on_bulk_products_is_rejected_and_falls_back(presentation):
    """The core new behavior: bulk/loose products CAN attempt isolation,
    but a result that erased almost all of the real product/pile must be
    rejected, not trusted -- never fabricate the missing product, just
    fall back to the honest Tier-1-only crop."""
    remover = DestructiveBackgroundRemover()
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, presentation, remover)

    assert remover.calls == 1
    assert result.background_isolation_status == BackgroundIsolationStatus.REJECTED
    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)  # still a usable, complete refined image


def test_fully_erasing_isolation_is_rejected():
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, PresentationType.BULK_TRAY, FullyErasingBackgroundRemover())

    assert result.background_isolation_status == BackgroundIsolationStatus.REJECTED
    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (CANVAS_SIZE, CANVAS_SIZE)


def test_partial_but_sufficient_isolation_is_applied_not_rejected():
    """~50% retained is well above MIN_RETAINED_AREA_RATIO -- a legitimate
    isolation that removed real background/tray should be trusted, not
    rejected out of excess caution."""
    crop_bytes = make_crop_bytes(400, 400)

    result = refine_product_image(crop_bytes, PresentationType.BULK_LOOSE, PartialBackgroundRemover())

    assert result.background_isolation_status == BackgroundIsolationStatus.APPLIED


def test_min_retained_area_ratio_is_conservative_but_not_absurdly_strict():
    """A basic sanity bound on the configured threshold itself -- not so
    strict that a normal, moderately-cropped isolation would be rejected,
    not so loose that a near-total erasure would be accepted."""
    assert 0.05 <= MIN_RETAINED_AREA_RATIO <= 0.35
