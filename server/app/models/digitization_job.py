from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DigitizationJobStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DigitizationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digitization_jobs"
    __table_args__ = (
        CheckConstraint(
            "total_items >= 0", name="ck_digitization_jobs_total_items_non_negative"
        ),
        CheckConstraint(
            "processed_items >= 0",
            name="ck_digitization_jobs_processed_items_non_negative",
        ),
        CheckConstraint(
            "failed_items >= 0",
            name="ck_digitization_jobs_failed_items_non_negative",
        ),
    )

    status: Mapped[DigitizationJobStatus] = mapped_column(
        SAEnum(
            DigitizationJobStatus,
            name="digitization_job_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=DigitizationJobStatus.PENDING,
    )
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    digitized_products: Mapped[list["DigitizedProduct"]] = relationship(  # noqa: F821
        "DigitizedProduct", back_populates="job", cascade="all, delete-orphan"
    )
