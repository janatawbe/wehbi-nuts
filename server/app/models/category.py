import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent: Mapped["Category | None"] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    products: Mapped[list["Product"]] = relationship(  # noqa: F821
        "Product", back_populates="category"
    )
