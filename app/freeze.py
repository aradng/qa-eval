from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis
from app.config import get_config
from app.models import Audit, Trade


def now() -> datetime:
    return datetime.now(UTC)


def window_of(executed_at: datetime, at: datetime) -> str:
    age = at - executed_at
    if age <= timedelta(days=get_config().WINDOW_A_DAYS):
        return "A"
    if age <= timedelta(days=get_config().WINDOW_B_DAYS):
        return "B"
    return "closed"


def recompute(trade: Trade) -> float:
    return float(trade.volume) * float(trade.price)


class Conflict(Exception):
    pass


class Forbidden(Exception):
    pass


async def edit_price(
    db: AsyncSession,
    trade_id: UUID,
    new_price: float,
    user_id: str,
    role: str,
) -> None:
    trade = await db.get(Trade, trade_id)
    if trade is None:
        raise KeyError(trade_id)
    window = window_of(trade.executed_at, now())
    # SEAL_ON_CLOCK treats a closed window as sealed without waiting for the
    # sweep to record it, so `trades.sealed` is not consulted for that case.
    if trade.sealed or (get_config().SEAL_ON_CLOCK and window == "closed"):
        raise Conflict("sealed")
    if window == "closed":
        raise Forbidden
    if window == "B" and role != "supervisor":
        raise Forbidden
    if window == "B":
        db.add(
            Audit(trade_id=trade_id, user_id=user_id, new_price=new_price)
        )
    trade.price = new_price
    trade.pnl = recompute(trade)


class _Lock:
    def __init__(self, name: str, ttl: int) -> None:
        self._name = f"qa:lock:{name}"
        self._ttl = ttl

    async def __aenter__(self) -> bool:
        # expires after ttl seconds whether or not the holder has finished.
        self._held = await redis().set(
            self._name, "1", nx=True, ex=self._ttl
        )
        return bool(self._held)

    async def __aexit__(self, *exc: object) -> None:
        if self._held:
            await redis().delete(self._name)


def lock(name: str, ttl: int) -> _Lock:
    return _Lock(name, ttl)


async def run_sweep_once(db: AsyncSession) -> int:
    async with lock("pnl-sweep", ttl=get_config().SWEEP_LOCK_TTL_S) as held:
        if not held:
            return 0
        cutoff = now() - timedelta(days=get_config().WINDOW_B_DAYS)
        due = (
            await db.scalars(
                select(Trade).where(
                    Trade.executed_at < cutoff,
                    Trade.sealed.is_(False),
                )
            )
        ).all()
        for trade in due:
            trade.sealed = True
        return len(due)
