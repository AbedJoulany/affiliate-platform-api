from typing import Literal

from pydantic import BaseModel


class DependencyStatus(BaseModel):
    status: Literal["up", "down"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[Literal["database", "redis"], DependencyStatus]
