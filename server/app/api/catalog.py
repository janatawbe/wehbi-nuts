from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.catalog_import import CatalogImportPreview, CatalogImportResult
from app.services.catalog_import_export_service import (
    CatalogImportError,
    apply_catalog_import,
    build_catalog_import_preview,
    export_catalog_xlsx,
)

router = APIRouter()

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export.xlsx")
def export_xlsx(db: Session = Depends(get_db)) -> Response:
    content = export_catalog_xlsx(db)
    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="wehbi-nuts-catalog.xlsx"'},
    )


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please upload an Excel (.xlsx) file.")
    return file.filename, await file.read()


@router.post("/import/preview", response_model=CatalogImportPreview)
async def preview_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CatalogImportPreview:
    filename, content = await _read_upload(file)
    try:
        return build_catalog_import_preview(db, settings, filename, content)
    except CatalogImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/import/confirm", response_model=CatalogImportResult)
async def confirm_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CatalogImportResult:
    filename, content = await _read_upload(file)
    try:
        return apply_catalog_import(db, settings, filename, content)
    except CatalogImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
