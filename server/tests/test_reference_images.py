"""Unit tests for Milestone 6's reference-image selection logic. Always
uses a temp directory (`tmp_path`), never the real, gitignored, and
possibly-absent server/reference-images/ tree -- these tests are fully
self-contained and don't depend on manually-curated local assets."""
from pathlib import Path

import pytest

from app.models.enums import PresentationType
from app.services.reference_images import MAX_REFERENCE_IMAGES, select_reference_images


def _make_file(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_bytes(b"fake-reference-image-bytes")
    return path


def test_bulk_tray_selects_bulk_and_seeds_prefixed_files(tmp_path: Path):
    _make_file(tmp_path, "bulk-nuts-01.png")
    _make_file(tmp_path, "seeds-01.png")
    _make_file(tmp_path, "packaged-01.png")

    selected = select_reference_images(PresentationType.BULK_TRAY, root=tmp_path)

    names = {p.name for p in selected}
    assert names == {"bulk-nuts-01.png", "seeds-01.png"}


def test_bulk_loose_selects_the_same_prefixes_as_bulk_tray(tmp_path: Path):
    _make_file(tmp_path, "bulk-nuts-01.png")
    _make_file(tmp_path, "seeds-01.png")

    selected = select_reference_images(PresentationType.BULK_LOOSE, root=tmp_path)

    assert {p.name for p in selected} == {"bulk-nuts-01.png", "seeds-01.png"}


@pytest.mark.parametrize(
    "presentation", [PresentationType.PACKAGED, PresentationType.JAR, PresentationType.BOTTLE]
)
def test_packaged_jar_bottle_select_packaged_prefixed_files_only(tmp_path: Path, presentation):
    _make_file(tmp_path, "packaged-01.png")
    _make_file(tmp_path, "bulk-nuts-01.png")

    selected = select_reference_images(presentation, root=tmp_path)

    assert [p.name for p in selected] == ["packaged-01.png"]


def test_other_presentation_selects_nothing():
    assert select_reference_images(PresentationType.OTHER) == []


def test_none_presentation_selects_nothing(tmp_path: Path):
    _make_file(tmp_path, "bulk-nuts-01.png")

    assert select_reference_images(None, root=tmp_path) == []


def test_missing_directory_returns_empty_list_not_an_error(tmp_path: Path):
    missing = tmp_path / "does-not-exist"

    assert select_reference_images(PresentationType.BULK_TRAY, root=missing) == []


def test_selection_is_capped_even_with_many_matching_files(tmp_path: Path):
    for i in range(5):
        _make_file(tmp_path, f"bulk-nuts-{i:02d}.png")

    selected = select_reference_images(PresentationType.BULK_TRAY, root=tmp_path)

    assert len(selected) == MAX_REFERENCE_IMAGES


def test_unsupported_extension_is_ignored(tmp_path: Path):
    _make_file(tmp_path, "bulk-notes.txt")
    _make_file(tmp_path, "bulk-nuts-01.png")

    selected = select_reference_images(PresentationType.BULK_TRAY, root=tmp_path)

    assert [p.name for p in selected] == ["bulk-nuts-01.png"]


def test_selection_is_deterministically_sorted(tmp_path: Path):
    _make_file(tmp_path, "bulk-z.png")
    _make_file(tmp_path, "bulk-a.png")

    selected = select_reference_images(PresentationType.BULK_TRAY, root=tmp_path)

    assert [p.name for p in selected] == ["bulk-a.png", "bulk-z.png"]


def test_a_directory_entry_is_never_treated_as_a_reference_file(tmp_path: Path):
    (tmp_path / "bulk-subdir").mkdir()
    _make_file(tmp_path, "bulk-real.png")

    selected = select_reference_images(PresentationType.BULK_TRAY, root=tmp_path)

    assert [p.name for p in selected] == ["bulk-real.png"]
