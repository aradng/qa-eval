from faststream.kafka import KafkaBroker
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import ConflictError, incr_by, set_checked
from app.config import get_config
from app.db import after_commit, session_ctx
from app.events import ChangeEvent, Row
from app.models import Total as TotalRow

broker = KafkaBroker(get_config().KAFKA_BOOTSTRAP)


class SkipCommit(Exception):
    """Raised to leave the message offset uncommitted, so the whole batch is
    redelivered later."""


type Applied = list[tuple[str, float, float]]  # product, new total, delta


def notional(row: Row) -> float:
    return row.volume * row.price


async def upsert_totals(
    db: AsyncSession, deltas: list[tuple[str, float]]
) -> Applied:
    if not deltas:
        return []
    merged: dict[str, tuple[float, int]] = {}
    for product, delta in deltas:
        total, count = merged.get(product, (0.0, 0))
        merged[product] = (total + delta, count + 1)

    stmt = insert(TotalRow).values(
        [
            {"product": p, "total": d, "trades": n}
            for p, (d, n) in merged.items()
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[TotalRow.product],
        set_={
            "total": TotalRow.total + stmt.excluded.total,
            "trades": TotalRow.trades + stmt.excluded.trades,
        },
    ).returning(TotalRow.product, TotalRow.total)

    rows = (await db.execute(stmt)).all()
    return [
        (product, float(total), merged[product][0])
        for product, total in rows
    ]


async def mirror_into_cache(applied: Applied) -> None:
    for product, total, delta in applied:
        if get_config().CACHE_INCR:
            # commutative, so concurrent writers cannot lose an update -- but
            # the cached value is now accumulated independently of the
            # database rather than copied from it.
            await incr_by(product, delta)
            continue
        try:
            await set_checked(product, total)
        except ConflictError:
            # another writer touched this key since the watch began. raising
            # here skips the offset commit, so the whole batch is redelivered
            # later.
            raise SkipCommit from None


async def handle_change(events: list[ChangeEvent], db: AsyncSession) -> None:
    """`db` is a transaction opened before this call. It COMMITS when this
    function returns normally, and ROLLS BACK if this function raises.
    Nothing before the return has committed.

    The message offset is committed only if this function returns normally;
    if it raises, the whole batch is redelivered later."""
    deltas: list[tuple[str, float]] = []
    for event in events:
        after, before = event.after, event.before
        if get_config().SKIP_BEFORE_IMAGE:
            # the `before` image is only present when the table's replica
            # identity is configured for it, so this treats every event as if
            # it were an insert.
            if after is not None:
                deltas.append((after.product, notional(after)))
            continue
        match event.op:
            case "c":
                if after is not None:
                    deltas.append((after.product, notional(after)))
            case "u":
                if after is not None and before is not None:
                    deltas.append(
                        (after.product, notional(after) - notional(before))
                    )
                elif after is not None:
                    deltas.append((after.product, notional(after)))
            case "d":
                if before is not None:
                    deltas.append((before.product, -notional(before)))

    applied = await upsert_totals(db, deltas)

    if get_config().MIRROR_AFTER_COMMIT:
        # the commit has NOT happened yet, so this defers the mirror to a
        # callback that runs after it. a failure there cannot roll the
        # transaction back, and cannot skip the offset commit either.
        after_commit(db, lambda: mirror_into_cache(applied))
    else:
        await mirror_into_cache(applied)


@broker.subscriber(
    get_config().TRADES_TOPIC, group_id=get_config().CONSUMER_GROUP, batch=True
)
async def on_change(events: list[ChangeEvent]) -> None:
    async with session_ctx() as db:
        await handle_change(events, db)
