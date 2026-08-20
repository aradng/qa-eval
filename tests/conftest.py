import os
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text

from app.cache import redis
from app.db import engine, session_ctx
from app.models import Audit, Base, Total, Trade

os.environ.setdefault(
    "POSTGRES_DSN", "postgresql+asyncpg://qa:qa@localhost:55432/qa"
)
os.environ.setdefault("REDIS_DSN", "redis://localhost:56379/0")


@pytest.fixture(scope="session", autouse=True)
async def schema() -> AsyncGenerator[None]:
    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
async def clean() -> AsyncGenerator[None]:
    async with session_ctx() as db:
        for model in (Audit, Total, Trade):
            await db.execute(delete(model))
    await redis().flushdb()
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    from app.api import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def make_event():
    """Build a change event for one trade."""

    def _make(
        product: str = "BRENT",
        volume: float = 1000.0,
        price: float = 80.0,
        op: str = "c",
        trade_id: UUID | None = None,
    ) -> dict:
        return {
            "op": op,
            "before": None,
            "after": {
                "trade_id": str(trade_id or uuid4()),
                "product": product,
                "volume": volume,
                "price": price,
                "side": "BUY",
                "executed_at": "2026-08-01T10:00:00Z",
            },
            "ts_ms": 1756000000000,
        }

    return _make


@pytest.fixture
async def db_total():
    """Read a product's total straight from Postgres, bypassing the cache."""

    async def _read(product: str) -> float | None:
        async with session_ctx() as db:
            row = await db.execute(
                text("select total from totals where product = :p"),
                {"p": product},
            )
            value = row.scalar_one_or_none()
            return None if value is None else float(value)

    return _read
