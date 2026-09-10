import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
from app.models.enums import StockStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        CheckConstraint(
            "discount_price IS NULL OR discount_price >= 0",
            name="ck_products_discount_price_non_negative",
        ),
        CheckConstraint(
            "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)",
            name="ck_products_ai_confidence_range",
        ),
    )

    sku: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    barcode: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    stock_status: Mapped[StockStatus] = mapped_column(
        SAEnum(
            StockStatus,
            name="stock_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=StockStatus.IN_STOCK,
    )

    image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_image: Mapped[str | None] = mapped_column(String(512), nullable=True)

    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    ai_raw_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    category: Mapped["Category | None"] = relationship(  # noqa: F821
        "Category", back_populates="products"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        "OrderItem", back_populates="product"
    )
    digitized_products: Mapped[list["DigitizedProduct"]] = relationship(  # noqa: F821
        "DigitizedProduct", back_populates="product"
    )
