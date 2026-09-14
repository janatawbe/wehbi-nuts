"""Milestone 8 catalog import/export -- Excel (.xlsx) only.

`Product` IS the real catalog entity (see Milestone 7's
digitizer_review_service._upsert_catalog_product) -- this module never
creates a second "publish" concept, never writes to `DigitizedProduct`,
and updates an existing `Product` row IN PLACE (same primary key) so any
Milestone 7 DigitizedProduct.product_id linkage into it is automatically
preserved without this module needing to know that linkage exists at all.

Preview and confirm-import share the exact same `_evaluate_import`
pipeline so they can never disagree about what a row means -- the only
difference is that `build_catalog_import_preview` never calls `db.add`/
`db.commit`, while `apply_catalog_import` does, once, at the end.
"""
import io
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.category import Category
from app.models.enums import StockStatus
from app.models.product import Product
from app.schemas.catalog_import import (
    CatalogImportFieldChange,
    CatalogImportPreview,
    CatalogImportResult,
    CatalogImportRow,
    CatalogImportRowResult,
    RowAction,
)


class CatalogImportError(Exception):
    """A client-safe, FILE-level import error (bad extension, unreadable
    workbook, missing/duplicate headers, too many rows/too large) --
    mirrors ReviewError/DigitizerUploadError elsewhere in this app.
    Distinct from a per-ROW validation failure, which never raises -- a
    bad row is reported as an `invalid` row so the rest of the file can
    still be evaluated; see `_evaluate_import`."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


SELLING_MODES = {"weight", "unit"}
STOCK_STATUSES = {status.value for status in StockStatus}

# (spreadsheet header, canonical field key) -- the single source of truth
# for column order/labels, shared by export AND import. Header matching on
# import is case-insensitive against these labels, so an export -> edit
# in Excel -> re-import round-trips without the admin needing to preserve
# exact header casing. Deliberately excludes internal/AI-only columns
# (created_at, updated_at, ai_confidence, ai_raw_result, needs_review,
# source_image) that aren't useful for a shop admin to read or edit.
COLUMNS: list[tuple[str, str]] = [
    ("ID", "id"),
    ("SKU", "sku"),
    ("Barcode", "barcode"),
    ("English Name", "name_en"),
    ("Arabic Name", "name_ar"),
    ("English Description", "description_en"),
    ("Arabic Description", "description_ar"),
    ("Category", "category"),
    ("Brand", "brand"),
    ("Selling Mode", "selling_mode"),
    ("Package Weight (kg)", "package_weight"),
    ("Price", "price"),
    ("Discount Price", "discount_price"),
    ("Stock Status", "stock_status"),
    ("Image", "image"),
]
FIELD_LABELS: dict[str, str] = {field_key: header for header, field_key in COLUMNS}
NUMERIC_FIELDS = {"price", "discount_price", "package_weight"}
# NOT NULL on Product -- a spreadsheet missing any of these can never
# produce a usable row, so the whole file is rejected up front rather than
# producing a file full of identically-broken "invalid" rows.
REQUIRED_FIELDS = {"name_en", "name_ar", "sku", "price"}
MAX_TEXT_LENGTHS = {"sku": 64, "barcode": 64, "name_en": 255, "name_ar": 255, "brand": 255, "image": 512}

# Friendly labels for the preview diff -- distinct from FIELD_LABELS
# because a diff talks about `category_id`/`selling_mode` (the Product
# attribute being changed), not the spreadsheet's own column name.
DIFF_LABELS: dict[str, str] = {
    "sku": "SKU",
    "barcode": "Barcode",
    "name_en": "English Name",
    "name_ar": "Arabic Name",
    "description_en": "English Description",
    "description_ar": "Arabic Description",
    "category_id": "Category",
    "brand": "Brand",
    "selling_mode": "Selling Mode",
    "package_weight": "Package Weight (kg)",
    "price": "Price",
    "discount_price": "Discount Price",
    "stock_status": "Stock Status",
    "image": "Image",
}
# canonical field key -> actual Product attribute name. `category` (the
# spreadsheet's resolved name) is applied as `category_id`; `selling_mode`
# and `package_weight` are applied as Product's pre-existing (Milestone 2)
# plain `unit`/`weight` fields -- see _upsert_catalog_product's own
# comment on why Product.unit is a free string, not a redesigned enum.
PRODUCT_ATTR_BY_FIELD: dict[str, str] = {
    "sku": "sku",
    "barcode": "barcode",
    "name_en": "name_en",
    "name_ar": "name_ar",
    "description_en": "description_en",
    "description_ar": "description_ar",
    "category_id": "category_id",
    "brand": "brand",
    "selling_mode": "unit",
    "package_weight": "weight",
    "price": "price",
    "discount_price": "discount_price",
    "stock_status": "stock_status",
    "image": "image",
}

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _neutralize_formula(value: str) -> str:
    """Excel formula-injection guard: a cell value that STARTS WITH a
    formula-triggering character is prefixed with a leading apostrophe,
    which Excel treats as literal text, never evaluating it. Applied to
    every free-text export column -- never to numeric columns, which can
    never carry attacker-controlled text (price/discount/weight are
    always non-negative decimals here)."""
    if value and value[0] in _FORMULA_PREFIXES:
        return f"'{value}"
    return value


def _decimal_to_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


# --------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------- #


def _product_row_values(product: Product) -> dict[str, str | None]:
    """The one place mapping a Product to plain display strings -- used
    both to build an export row and (via `_display_value`-style handling
    below) to show a preview diff's "current" side, so export and preview
    can never describe a product differently."""
    return {
        "id": str(product.id),
        "sku": product.sku,
        "barcode": product.barcode,
        "name_en": product.name_en,
        "name_ar": product.name_ar,
        "description_en": product.description_en,
        "description_ar": product.description_ar,
        "category": product.category.name_en if product.category else None,
        "brand": product.brand,
        "selling_mode": product.unit,
        "package_weight": _decimal_to_str(product.weight),
        "price": _decimal_to_str(product.price),
        "discount_price": _decimal_to_str(product.discount_price),
        "stock_status": product.stock_status.value if product.stock_status else None,
        "image": product.image,
    }


def _all_products_for_export(db: Session) -> list[Product]:
    stmt = select(Product).order_by(Product.created_at.asc())
    return list(db.scalars(stmt).all())


def export_catalog_xlsx(db: Session) -> bytes:
    """A clean, single-sheet workbook: one header row (frozen), one row
    per catalog Product, readable column widths. No decorative styling."""
    products = _all_products_for_export(db)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    headers = [header for header, _ in COLUMNS]
    sheet.append(headers)
    sheet.freeze_panes = "A2"

    for product in products:
        values = _product_row_values(product)
        row: list[Any] = []
        for _, field_key in COLUMNS:
            value = values[field_key]
            if value is None:
                row.append(None)
            elif field_key in NUMERIC_FIELDS:
                row.append(Decimal(value))
            else:
                row.append(_neutralize_formula(str(value)))
        sheet.append(row)

    for index, header in enumerate(headers, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = max(12, min(40, len(header) + 6))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------- #
# Import: file reading
# --------------------------------------------------------------------- #


def _read_xlsx_rows(content: bytes) -> list[list[Any]]:
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises several distinct exception types for a bad file
        raise CatalogImportError(
            "Could not read the uploaded file -- make sure it is a valid .xlsx file."
        ) from exc
    try:
        sheet = workbook.worksheets[0]
        rows: list[list[Any]] = []
        for raw_row in sheet.iter_rows(values_only=True):
            rows.append([cell if not isinstance(cell, str) else _clean_str(cell) for cell in raw_row])
        return rows
    finally:
        workbook.close()


def _read_workbook(
    filename: str, content: bytes, *, max_size_bytes: int, max_rows: int
) -> tuple[list[Any], list[list[Any]]]:
    # Filenames never touch the filesystem anywhere in this module --
    # everything is parsed in memory -- so this is purely an extension
    # sniff, never a path.
    extension = filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
    if extension != "xlsx":
        raise CatalogImportError("Please upload an Excel (.xlsx) file.")
    if len(content) == 0:
        raise CatalogImportError("The uploaded file is empty.")
    if len(content) > max_size_bytes:
        raise CatalogImportError(f"The uploaded file is too large (max {max_size_bytes // (1024 * 1024)} MB).")

    all_rows = _read_xlsx_rows(content)
    all_rows = [row for row in all_rows if any(cell not in (None, "") for cell in row)]
    if not all_rows:
        raise CatalogImportError("The uploaded file has no header row.")

    header_row, *data_rows = all_rows
    if not data_rows:
        raise CatalogImportError("The uploaded file has no data rows.")
    if len(data_rows) > max_rows:
        raise CatalogImportError(f"The uploaded file has too many rows (max {max_rows}).")

    return header_row, data_rows


def _map_headers(header_row: list[Any]) -> dict[str, int]:
    label_to_field = {header.casefold(): field_key for header, field_key in COLUMNS}
    seen: dict[str, int] = {}
    field_index: dict[str, int] = {}
    for index, raw_header in enumerate(header_row):
        if raw_header is None:
            continue
        normalized = str(raw_header).strip().casefold()
        if normalized == "":
            continue
        if normalized in seen:
            raise CatalogImportError(f"Duplicate column header: '{raw_header}'.")
        seen[normalized] = index
        field_key = label_to_field.get(normalized)
        if field_key is not None:
            field_index[field_key] = index

    missing = REQUIRED_FIELDS - field_index.keys()
    if missing:
        missing_labels = ", ".join(sorted(FIELD_LABELS[key] for key in missing))
        raise CatalogImportError(f"Missing required column(s): {missing_labels}.")
    return field_index


def _row_dict(data_row: list[Any], field_index: dict[str, int]) -> dict[str, Any]:
    return {key: (data_row[index] if index < len(data_row) else None) for key, index in field_index.items()}


# --------------------------------------------------------------------- #
# Import: per-row normalization + validation
# --------------------------------------------------------------------- #


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def _parse_decimal(value: Any, label: str) -> tuple[Decimal | None, str | None]:
    if value is None:
        return None, None
    try:
        return Decimal(str(value).strip()), None
    except (InvalidOperation, ValueError):
        return None, f"{label} must be a valid number."


def _display_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, StockStatus):
        return value.value
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


@dataclass
class _RowEvaluation:
    row_number: int
    action: RowAction
    product: Product | None
    errors: list[str]
    changes: list[CatalogImportFieldChange]
    values: dict[str, Any] = field(default_factory=dict)
    sku: str | None = None
    name_en: str | None = None


def _normalize_row(
    raw: dict[str, Any],
    category_by_key: dict[str, Category],
) -> tuple[dict[str, Any], list[str]]:
    """Turns one row's raw spreadsheet cells into typed Product field
    values (or None) plus every validation error found. Never raises --
    a single bad row must never stop the rest of the file being
    evaluated; it just carries its own errors and is reported `invalid`."""
    errors: list[str] = []
    values: dict[str, Any] = {}

    raw_id = raw.get("id")
    parsed_id: uuid.UUID | None = None
    if raw_id is not None:
        try:
            parsed_id = uuid.UUID(str(raw_id).strip())
        except ValueError:
            errors.append(f"'{raw_id}' is not a valid Product ID.")
    values["id"] = parsed_id

    sku = _clean_str(raw.get("sku"))
    if not sku:
        errors.append("SKU is required.")
    elif len(sku) > MAX_TEXT_LENGTHS["sku"]:
        errors.append(f"SKU must be {MAX_TEXT_LENGTHS['sku']} characters or fewer.")
    values["sku"] = sku

    name_en = _clean_str(raw.get("name_en"))
    if not name_en:
        errors.append("English name is required.")
    elif len(name_en) > MAX_TEXT_LENGTHS["name_en"]:
        errors.append(f"English name must be {MAX_TEXT_LENGTHS['name_en']} characters or fewer.")
    values["name_en"] = name_en

    name_ar = _clean_str(raw.get("name_ar"))
    if not name_ar:
        errors.append("Arabic name is required.")
    elif len(name_ar) > MAX_TEXT_LENGTHS["name_ar"]:
        errors.append(f"Arabic name must be {MAX_TEXT_LENGTHS['name_ar']} characters or fewer.")
    values["name_ar"] = name_ar

    barcode = _clean_str(raw.get("barcode"))
    if barcode and len(barcode) > MAX_TEXT_LENGTHS["barcode"]:
        errors.append(f"Barcode must be {MAX_TEXT_LENGTHS['barcode']} characters or fewer.")
    values["barcode"] = barcode

    values["description_en"] = _clean_str(raw.get("description_en"))
    values["description_ar"] = _clean_str(raw.get("description_ar"))

    brand = _clean_str(raw.get("brand"))
    if brand and len(brand) > MAX_TEXT_LENGTHS["brand"]:
        errors.append(f"Brand must be {MAX_TEXT_LENGTHS['brand']} characters or fewer.")
    values["brand"] = brand

    image = _clean_str(raw.get("image"))
    if image and len(image) > MAX_TEXT_LENGTHS["image"]:
        errors.append(f"Image must be {MAX_TEXT_LENGTHS['image']} characters or fewer.")
    values["image"] = image

    category_value = _clean_str(raw.get("category"))
    category: Category | None = None
    if category_value is not None:
        category = category_by_key.get(category_value.casefold())
        if category is None:
            errors.append(f"Category '{category_value}' does not exist.")
    values["category_id"] = category.id if category else None
    values["_category"] = category

    selling_mode = _clean_str(raw.get("selling_mode"))
    if selling_mode is None:
        values["selling_mode"] = None
    elif selling_mode.casefold() not in SELLING_MODES:
        errors.append("Selling mode must be 'weight' or 'unit'.")
        values["selling_mode"] = None
    else:
        values["selling_mode"] = selling_mode.casefold()

    stock_status_raw = _clean_str(raw.get("stock_status"))
    if stock_status_raw is None:
        values["stock_status"] = StockStatus.IN_STOCK
    elif stock_status_raw.casefold() not in STOCK_STATUSES:
        errors.append("Stock status must be 'in_stock', 'low_stock', or 'out_of_stock'.")
        values["stock_status"] = None
    else:
        values["stock_status"] = StockStatus(stock_status_raw.casefold())

    price, price_error = _parse_decimal(raw.get("price"), "Price")
    if price_error:
        errors.append(price_error)
    elif price is None:
        errors.append("Price is required.")
    elif price < 0:
        errors.append("Price cannot be negative.")
    values["price"] = price

    discount_price, discount_error = _parse_decimal(raw.get("discount_price"), "Discount price")
    if discount_error:
        errors.append(discount_error)
    elif discount_price is not None and discount_price < 0:
        errors.append("Discount price cannot be negative.")
    values["discount_price"] = discount_price

    package_weight, weight_error = _parse_decimal(raw.get("package_weight"), "Package weight")
    if weight_error:
        errors.append(weight_error)
    elif package_weight is not None and package_weight < 0:
        errors.append("Package weight cannot be negative.")
    values["package_weight"] = package_weight

    # Mirrors Milestone 7's own approval-time consistency rule (see
    # digitizer_review_service.validate_for_approval): a weight-mode
    # product is priced per kilogram, so a printed package weight doesn't
    # apply to it.
    if values["selling_mode"] == "weight" and package_weight not in (None, Decimal("0")):
        errors.append("Weight-mode products must not have a package weight.")

    return values, errors


def _evaluate_import(
    db: Session, settings: Settings, filename: str, content: bytes
) -> list[_RowEvaluation]:
    header_row, data_rows = _read_workbook(
        filename,
        content,
        max_size_bytes=settings.catalog_import_max_file_size_bytes,
        max_rows=settings.catalog_import_max_rows,
    )
    field_index = _map_headers(header_row)

    category_by_key: dict[str, Category] = {}
    for category in db.scalars(select(Category)).all():
        category_by_key.setdefault(category.slug.casefold(), category)
        category_by_key.setdefault(category.name_en.casefold(), category)

    existing_products = list(db.scalars(select(Product)).all())
    existing_by_id = {product.id: product for product in existing_products}
    existing_by_sku = {product.sku: product for product in existing_products}
    existing_by_barcode = {product.barcode: product for product in existing_products if product.barcode}

    # Pass 1: per-row intrinsic validation (never needs to see other rows).
    pending: list[tuple[int, dict[str, Any], list[str]]] = []
    for offset, data_row in enumerate(data_rows):
        row_number = offset + 2  # header is row 1 -- matches what the admin sees in Excel
        raw = _row_dict(data_row, field_index)
        values, errors = _normalize_row(raw, category_by_key)
        pending.append((row_number, values, errors))

    # Pass 2: duplicate identifiers WITHIN this file -- flag every row
    # sharing a non-blank id/sku with another row in the same file, never
    # just one of them, and never let any of them be applied (see
    # apply_catalog_import).
    ids_seen: dict[uuid.UUID, list[int]] = defaultdict(list)
    skus_seen: dict[str, list[int]] = defaultdict(list)
    for index, (_, values, _errors) in enumerate(pending):
        if values["id"] is not None:
            ids_seen[values["id"]].append(index)
        if values["sku"]:
            skus_seen[values["sku"]].append(index)
    for indices in ids_seen.values():
        if len(indices) > 1:
            for index in indices:
                pending[index][2].append("Duplicate Product ID in this file.")
    for indices in skus_seen.values():
        if len(indices) > 1:
            for index in indices:
                pending[index][2].append("Duplicate SKU in this file.")

    # Pass 3: match against the current catalog and classify.
    evaluations: list[_RowEvaluation] = []
    for row_number, values, errors in pending:
        matched_by_id = existing_by_id.get(values["id"]) if values["id"] is not None else None
        if values["id"] is not None and matched_by_id is None:
            errors.append(f"Product ID '{values['id']}' does not match any existing product.")

        matched_by_sku = existing_by_sku.get(values["sku"]) if values["sku"] else None
        product = matched_by_id or matched_by_sku
        if matched_by_id is not None and matched_by_sku is not None and matched_by_id.id != matched_by_sku.id:
            errors.append(f"SKU '{values['sku']}' is already used by another product.")

        if values["barcode"]:
            clash = existing_by_barcode.get(values["barcode"])
            if clash is not None and (product is None or clash.id != product.id):
                errors.append(f"Barcode '{values['barcode']}' is already used by another product.")

        action, changes = _classify(values, errors, product)
        evaluations.append(
            _RowEvaluation(
                row_number=row_number,
                action=action,
                product=product,
                errors=errors,
                changes=changes,
                values=values,
                sku=values["sku"],
                name_en=values["name_en"],
            )
        )

    return evaluations


def _classify(
    values: dict[str, Any], errors: list[str], product: Product | None
) -> tuple[RowAction, list[CatalogImportFieldChange]]:
    if errors:
        return "invalid", []
    if product is None:
        return "new", []

    changes: list[CatalogImportFieldChange] = []
    for field_key, attr in PRODUCT_ATTR_BY_FIELD.items():
        old_value = getattr(product, attr)
        new_value = values[field_key]
        if old_value != new_value:
            if field_key == "category_id":
                old_display = product.category.name_en if product.category else None
                new_display = values["_category"].name_en if values["_category"] else None
            else:
                old_display, new_display = _display_value(old_value), _display_value(new_value)
            changes.append(
                CatalogImportFieldChange(field=field_key, label=DIFF_LABELS[field_key], old=old_display, new=new_display)
            )

    return ("update" if changes else "unchanged"), changes


# --------------------------------------------------------------------- #
# Import: preview (read-only) and confirm (writes)
# --------------------------------------------------------------------- #


def build_catalog_import_preview(
    db: Session, settings: Settings, filename: str, content: bytes
) -> CatalogImportPreview:
    """Parses, validates, and classifies every row -- makes ZERO database
    writes. Shares `_evaluate_import` with `apply_catalog_import` so the
    two can never disagree about what a row means."""
    evaluations = _evaluate_import(db, settings, filename, content)
    counts = Counter(evaluation.action for evaluation in evaluations)
    rows = [
        CatalogImportRow(
            row_number=evaluation.row_number,
            action=evaluation.action,
            product_id=evaluation.product.id if evaluation.product else None,
            sku=evaluation.sku,
            name_en=evaluation.name_en,
            errors=evaluation.errors,
            changes=evaluation.changes,
        )
        for evaluation in evaluations
    ]
    return CatalogImportPreview(
        filename=filename,
        total_rows=len(evaluations),
        new_count=counts.get("new", 0),
        update_count=counts.get("update", 0),
        unchanged_count=counts.get("unchanged", 0),
        invalid_count=counts.get("invalid", 0),
        rows=rows,
    )


def apply_catalog_import(
    db: Session, settings: Settings, filename: str, content: bytes
) -> CatalogImportResult:
    """Re-parses and re-validates the file (never trusts a client-supplied
    preview) and applies every valid row in ONE transaction: every new/
    updated Product is added to the session, then committed together. An
    unexpected database-level failure rolls back the entire batch rather
    than leaving a half-applied import -- this is the only case where
    "partial" isn't supported; validation-failed rows are always excluded
    and always reported explicitly, never silently skipped.

    Never touches DigitizedProduct: a matched row updates the existing
    Product row IN PLACE (same primary key), so any Milestone 7
    DigitizedProduct.product_id linkage into it stays valid automatically,
    and the historical DigitizedProduct review record itself is never
    rewritten just because the catalog row changed here.
    """
    evaluations = _evaluate_import(db, settings, filename, content)

    created = updated = unchanged = 0
    failures: list[CatalogImportRowResult] = []

    try:
        for evaluation in evaluations:
            if evaluation.action == "invalid":
                failures.append(
                    CatalogImportRowResult(
                        row_number=evaluation.row_number,
                        sku=evaluation.sku,
                        name_en=evaluation.name_en,
                        errors=evaluation.errors,
                    )
                )
                continue
            if evaluation.action == "unchanged":
                unchanged += 1
                continue

            if evaluation.action == "new":
                product = Product()
                created += 1
            else:
                product = evaluation.product
                updated += 1

            for field_key, attr in PRODUCT_ATTR_BY_FIELD.items():
                setattr(product, attr, evaluation.values[field_key])
            db.add(product)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return CatalogImportResult(created=created, updated=updated, unchanged=unchanged, failed=len(failures), failures=failures)
