import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
from app.models.enums import SellingMode
from app.models.mixins import UUIDPrimaryKeyMixin, utcnow


class OrderItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint(
            "unit_price >= 0", name="ck_order_items_unit_price_non_negative"
        ),
        CheckConstraint(
            "line_total >= 0", name="ck_order_items_line_total_non_negative"
        ),
        CheckConstraint(
            "package_weight IS NULL OR package_weight >= 0",
            name="ck_order_items_package_weight_non_negative",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Snapshots taken at order time so historical orders stay accurate even
    # if the underlying Product is later renamed, repriced, repurposed
    # (selling_mode/package_weight changed), or deleted (product_id itself
    # goes NULL, per the FK's ondelete=SET NULL above).
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Arabic snapshot of the same name, taken alongside product_name so the
    # storefront can show the order back to the customer in whichever
    # language they placed it in. Nullable because a product's Arabic name
    # itself is optional (Product.name_ar) -- when it was empty at order
    # time, the frontend's existing localizedField() fallback to English
    # applies, exactly as it does for every other bilingual field.
    product_name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Milestone 10: how THIS line was actually sold, snapshotted -- reuses
    # the existing `selling_mode` Postgres enum type (already created for
    # DigitizedProduct.selling_mode; see the M10 migration, which does not
    # recreate it). Independent of whatever Product.unit says today: a
    # product's selling mode could change after this order was placed, and
    # this column must keep describing what actually happened at purchase
    # time either way.
    selling_mode: Mapped[SellingMode] = mapped_column(
        SAEnum(
            SellingMode,
            name="selling_mode",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    # Kilograms for a WEIGHT line (e.g. 0.300 for 300 g); a plain item count
    # for a UNIT line (e.g. 2.000). Numeric(10, 3) -- same precision as
    # Product.weight -- rather than Integer, specifically so a weight-mode
    # purchase can be represented at all; see the M10 migration for why
    # this replaced the original Milestone 2 Integer column.
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    # For a WEIGHT line: price per kilogram at order time. For a UNIT line:
    # the fixed price per package at order time. Either way, always
    # `line_total = unit_price * quantity` (kg for weight, count for unit)
    # -- one formula for both modes, matching how Product.price already
    # carries this same dual meaning throughout the storefront.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Snapshot of Product.weight (kg) at order time, ONLY meaningful for a
    # UNIT line whose product has a known package weight (e.g. "250 g
    # bag") -- always NULL for a WEIGHT line, whose purchased amount is
    # already fully captured by `quantity` above. Purely descriptive: never
    # used in any price calculation.
    package_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped["Order"] = relationship("Order", back_populates="items")  # noqa: F821
    product: Mapped["Product | None"] = relationship(  # noqa: F821
        "Product", back_populates="order_items"
    )
