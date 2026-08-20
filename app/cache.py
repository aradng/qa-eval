from functools import lru_cache

from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.config import get_config


class ConflictError(Exception):
    pass


def cache_key(product: str) -> str:
    return f"qa:total:{product}"


@lru_cache
def redis() -> Redis:
    return Redis.from_url(get_config().REDIS_DSN, decode_responses=True)


async def get_total(product: str) -> float | None:
    raw = await redis().get(cache_key(product))
    return None if raw is None else float(raw)


async def set_checked(product: str, total: float) -> None:
    """Overwrite the cached total, aborting if another writer touched the key
    since this call began."""
    key = cache_key(product)
    async with redis().pipeline() as pipe:
        try:
            await pipe.watch(key)
            await pipe.get(key)
            pipe.multi()
            pipe.set(key, total)
            await pipe.execute()
        except WatchError as exc:
            raise ConflictError(key) from exc


async def incr_by(product: str, delta: float) -> None:
    await redis().incrbyfloat(cache_key(product), delta)
