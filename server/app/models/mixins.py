import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.types import GUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
