import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name_en: str = Field(min_length=1, max_length=255)
    name_ar: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    name_ar: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
