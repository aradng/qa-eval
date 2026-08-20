from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.config import get_config
from app.db import session
from app.freeze import Conflict, Forbidden, edit_price, run_sweep_once
from app.models import Trade
from app.schemas import SCHEMA, Binary, Constant, Operator, Query

Db = Annotated[AsyncSession, Depends(session)]

app = FastAPI(title="notional totals")


@app.get("/health")
async def health() -> dict[str, str]:
    if get_config().DEMO_HEALTH_BUG:
        return {"status": "OK"}
    return {"status": "ok"}


@app.get("/total/{product}")
async def read_total(product: str) -> float:
    total = await cache.get_total(product)
    if total is None:
        raise HTTPException(404, "unknown product")
    return total


@app.get("/total/query/schema")
async def get_schema() -> dict[str, Any]:
    return SCHEMA


async def evaluate(node: Query) -> float:
    if isinstance(node, Constant):
        return node.value
    if isinstance(node, Binary):
        values = [await evaluate(child) for child in node.children]
        result = values[0]
        for value in values[1:]:
            match node.op:
                case Operator.ADD:
                    result += value
                case Operator.SUB:
                    result -= value
                case Operator.MUL:
                    result *= value
                case Operator.DIV:
                    result /= value
        return result
    total = await cache.get_total(node.name)
    if total is None:
        raise HTTPException(404, f"unknown product: {node.name}")
    return total


@app.post("/total/query")
async def run_query(expr: Query) -> float:
    return await evaluate(expr)


class TradeOut(BaseModel):
    trade_id: UUID
    product: str
    price: float
    pnl: float | None
    sealed: bool


@app.get("/trade/{trade_id}")
async def read_trade(trade_id: UUID, db: Db) -> TradeOut:
    trade = await db.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(404, "unknown trade")
    return TradeOut(
        trade_id=trade.trade_id,
        product=trade.product,
        price=float(trade.price),
        pnl=None if trade.pnl is None else float(trade.pnl),
        sealed=trade.sealed,
    )


class PriceEdit(BaseModel):
    new_price: float
    user_id: str
    role: str = "trader"


@app.patch("/trade/{trade_id}/price", status_code=204)
async def patch_price(trade_id: UUID, body: PriceEdit, db: Db) -> None:
    try:
        await edit_price(
            db, trade_id, body.new_price, body.user_id, body.role
        )
    except KeyError:
        raise HTTPException(404, "unknown trade") from None
    except Conflict:
        raise HTTPException(409, "sealed") from None
    except Forbidden:
        raise HTTPException(403, "not permitted") from None


@app.post("/sweep")
async def sweep(db: Db) -> int:
    return await run_sweep_once(db)
