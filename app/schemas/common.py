from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(ORMModel):
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    total: int
    skip: int
    limit: int


class IDSchema(ORMModel):
    id: UUID
