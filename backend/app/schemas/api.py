from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    release_type: str
    product: str
    state: str
    severity: str
    owner_id: str | None
    version: int
    approval_status: str | None
    scenario_key: str
    created_at: datetime
    finding_count: int = 0


class DecisionInput(BaseModel):
    decision: str
    rationale: str = Field(min_length=1, max_length=1000)


class PostInput(BaseModel):
    approval_token: str
    idempotency_key: str = Field(min_length=8, max_length=80)


class ReplayInput(BaseModel):
    scenario_key: str
