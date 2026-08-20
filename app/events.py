from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Row(BaseModel):
    trade_id: UUID
    product: str
    volume: float
    price: float
    side: str | None = None
    executed_at: datetime


class ChangeEvent(BaseModel):
    """One row change, as a change-data-capture connector emits it."""

    op: Literal["c", "u", "d"]
    before: Row | None = None
    after: Row | None = None
    ts_ms: int
