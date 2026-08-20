from functools import lru_cache

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    POSTGRES_DSN: str = "postgresql+asyncpg://qa:qa@localhost:55432/qa"
    REDIS_DSN: str = "redis://localhost:56379/0"
    KAFKA_BOOTSTRAP: str = "localhost:59092"
    SCHEMA_REGISTRY: str = "http://localhost:58081"

    TRADES_TOPIC: str = "db.public.trades"
    CONSUMER_GROUP: str = "totals"

    WINDOW_A_DAYS: int = 2
    WINDOW_B_DAYS: int = 5
    SWEEP_LOCK_TTL_S: int = 30

    # Every flag below defaults to off. With all of them off the service is
    # correct, as far as we know. Turning one on arms one fault at runtime.
    SCHEMA_DOC_MODE: bool = False
    SKIP_BEFORE_IMAGE: bool = False
    MIRROR_AFTER_COMMIT: bool = False
    CACHE_INCR: bool = False
    SEAL_ON_CLOCK: bool = False
    DEMO_HEALTH_BUG: bool = False


@lru_cache
def get_config() -> Config:
    return Config()


cfg = get_config()
