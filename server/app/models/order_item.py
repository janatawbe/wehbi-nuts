import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
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
    # if the underlying Product is later renamed, repriced, or deleted.
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

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
