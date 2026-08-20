"""Phase 0 — given. These prove the system works end to end."""

import pytest

from app.consumer import handle_change
from app.db import session_ctx
from app.events import ChangeEvent

pytestmark = pytest.mark.phase0


async def test_a_change_event_lands_in_the_cached_total(
    client, make_event, db_total
):
    events = [ChangeEvent.model_validate(make_event(volume=10, price=5))]
    async with session_ctx() as db:
        await handle_change(events, db)

    assert await db_total("BRENT") == 50.0

    response = await client.get("/total/BRENT")
    assert response.status_code == 200
    assert response.json() == 50.0


async def test_totals_accumulate_across_batches(make_event, db_total):
    for _ in range(3):
        async with session_ctx() as db:
            await handle_change(
                [ChangeEvent.model_validate(make_event(volume=1, price=100))],
                db,
            )
    assert await db_total("BRENT") == 300.0


async def test_a_valid_query_returns_a_number(client, make_event):
    async with session_ctx() as db:
        await handle_change(
            [ChangeEvent.model_validate(make_event(volume=2, price=50))], db
        )

    response = await client.post(
        "/total/query",
        json={"kind": "total", "product_name": "BRENT"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == 100.0


async def test_the_schema_endpoint_serves_a_schema(client):
    response = await client.get("/total/query/schema")
    assert response.status_code == 200
    assert "$defs" in response.json()
