from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_config


@lru_cache
def engine() -> AsyncEngine:
    return create_async_engine(get_config().POSTGRES_DSN, pool_pre_ping=True)


@lru_cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine(), expire_on_commit=False, autoflush=False
    )


type AfterCommit = Callable[[], Awaitable[Any]]


def after_commit(session: AsyncSession, fn: AfterCommit) -> None:
    session.info.setdefault("after_commit", []).append(fn)


async def _run_after_commit(session: AsyncSession) -> None:
    for fn in session.info.pop("after_commit", []):
        await fn()


async def session() -> AsyncGenerator[AsyncSession]:
    """A transaction that commits when the caller returns and rolls back if
    the caller raises. Callbacks registered with `after_commit` run once the
    commit has landed; a failure in one of them cannot undo it."""
    async with session_factory()() as s:
        async with s.begin():
            yield s
        await _run_after_commit(s)


@asynccontextmanager
async def session_ctx() -> AsyncGenerator[AsyncSession]:
    async with session_factory()() as s:
        async with s.begin():
            yield s
        await _run_after_commit(s)
