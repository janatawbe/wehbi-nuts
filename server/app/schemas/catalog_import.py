import uuid
from typing import Literal

from pydantic import BaseModel

RowAction = Literal["new", "update", "unchanged", "invalid"]


class CatalogImportFieldChange(BaseModel):
    """One field that differs between the spreadsheet row and the current
    catalog Product -- both sides already formatted as plain display
    strings, so the frontend never has to know the underlying field types."""

    field: str
    label: str
    old: str | None
    new: str | None


class CatalogImportRow(BaseModel):
    """One row's outcome from `build_catalog_import_preview`/
    `apply_catalog_import` -- the same evaluation feeds both, so preview
    and confirm can never disagree about what a row means."""

    row_number: int
    action: RowAction
    product_id: uuid.UUID | None = None
    sku: str | None = None
    name_en: str | None = None
    errors: list[str] = []
    changes: list[CatalogImportFieldChange] = []


class CatalogImportPreview(BaseModel):
    filename: str
    total_rows: int
    new_count: int
    update_count: int
    unchanged_count: int
    invalid_count: int
    rows: list[CatalogImportRow]


class CatalogImportRowResult(BaseModel):
    row_number: int
    sku: str | None = None
    name_en: str | None = None
    errors: list[str] = []


class CatalogImportResult(BaseModel):
    created: int
    updated: int
    unchanged: int
    failed: int
    failures: list[CatalogImportRowResult] = []
