import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DigitizationJobStatus


class DigitizationJobBase(BaseModel):
    status: DigitizationJobStatus = DigitizationJobStatus.PENDING
    total_items: int = Field(default=0, ge=0)
    processed_items: int = Field(default=0, ge=0)
    failed_items: int = Field(default=0, ge=0)
    error_message: str | None = None


class DigitizationJobCreate(BaseModel):
    total_items: int = Field(default=0, ge=0)


class DigitizationJobUpdate(BaseModel):
    status: DigitizationJobStatus | None = None
    total_items: int | None = Field(default=None, ge=0)
    processed_items: int | None = Field(default=None, ge=0)
    failed_items: int | None = Field(default=None, ge=0)
    error_message: str | None = None


class DigitizationJobRead(DigitizationJobBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
