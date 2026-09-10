from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import OrderStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_orders_subtotal_non_negative"),
        CheckConstraint("total >= 0", name="ck_orders_total_non_negative"),
    )

    order_number: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_area: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(
            OrderStatus,
            name="order_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=OrderStatus.PENDING,
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
