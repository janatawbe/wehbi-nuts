"""Milestone 6: selects local style/presentation reference images for AI
image refinement, based on a product's `presentation`.

These are development/runtime GUIDANCE assets only -- see
server/reference-images/README.md. They are never application/product
data, never stored in the database, and never sent to a customer; the
actual product shown in a refined image always comes from the real
Milestone 4 crop, never from a reference image.
"""
from pathlib import Path

from app.models.enums import PresentationType

# server/app/services/reference_images.py -> parents[2] == server/
_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "reference-images" / "product-refinement"

_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# Filename PREFIX convention (see server/reference-images/README.md) --
# extensible by dropping a correctly-prefixed file into the directory, no
# code change required to pick up a new reference image.
_PRESENTATION_PREFIXES: dict[PresentationType, tuple[str, ...]] = {
    PresentationType.BULK_TRAY: ("bulk-", "seeds-"),
    PresentationType.BULK_LOOSE: ("bulk-", "seeds-"),
    PresentationType.PACKAGED: ("packaged-",),
    PresentationType.JAR: ("packaged-",),
    PresentationType.BOTTLE: ("packaged-",),
}

# At most this many reference images are selected per refinement request.
# OpenRouter's Images API caps total input_references at 3 for
# google/gemini-2.5-flash-image, and the primary M4 crop always occupies
# one of those three slots (see ai/image_editing_refiner.py) -- so at most
# 2 style references are ever needed/selected here, not "every matching
# file every time."
MAX_REFERENCE_IMAGES = 2


def select_reference_images(
    presentation: PresentationType | None, root: Path | None = None
) -> list[Path]:
    """Returns up to MAX_REFERENCE_IMAGES reference image paths suitable
    for `presentation`, or an empty list if none apply -- including for
    `other`/unknown presentations (no reliable basis to pick a style), or
    if the reference directory doesn't exist locally at all (it is
    gitignored and optional; a fresh clone or CI environment need not have
    it, see server/reference-images/README.md). Sorted for a
    deterministic, reproducible selection.
    """
    prefixes = _PRESENTATION_PREFIXES.get(presentation) if presentation else None
    if not prefixes:
        return []

    directory = root if root is not None else _DEFAULT_ROOT
    if not directory.is_dir():
        return []

    matches = sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in _SUPPORTED_EXTENSIONS
        and path.name.lower().startswith(prefixes)
    )
    return matches[:MAX_REFERENCE_IMAGES]
