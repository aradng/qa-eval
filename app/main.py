import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import app
from app.consumer import broker
from app.db import engine
from app.models import Base

logging.basicConfig(level=logging.INFO)


async def create_schema() -> None:
    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_schema()
    await broker.start()
    yield
    await broker.close()


app.router.lifespan_context = lifespan


if __name__ == "__main__":
    asyncio.run(create_schema())
