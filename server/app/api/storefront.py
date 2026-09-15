import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.storefront import StorefrontCategoryRead, StorefrontProductRead
from app.services.storefront_service import (
    get_storefront_product,
    list_storefront_categories,
    list_storefront_products,
)

router = APIRouter()


@router.get("/categories", response_model=list[StorefrontCategoryRead])
def list_categories(db: Session = Depends(get_db)) -> list[StorefrontCategoryRead]:
    return list_storefront_categories(db)


@router.get("/products", response_model=list[StorefrontProductRead])
def list_products(
    category: str | None = Query(default=None, description="Category slug to filter by"),
    search: str | None = Query(default=None, description="Matches English or Arabic product name"),
    limit: int | None = Query(default=None, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[StorefrontProductRead]:
    return list_storefront_products(db, category_slug=category, search=search, limit=limit)


@router.get("/products/{product_id}", response_model=StorefrontProductRead)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> StorefrontProductRead:
    product = get_storefront_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product
