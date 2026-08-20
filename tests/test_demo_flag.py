"""The pattern, worked through on a throwaway fault.

`DEMO_HEALTH_BUG` makes `GET /health` answer `{"status": "OK"}` instead of
`{"status": "ok"}`. It is not one of the faults you are asked to find; it is
here so the shape of a flag test is not left to guesswork.

Two ways to express it. Both belong in CI; which one you reach for depends on
whether the whole suite runs per configuration or not.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from tests.flags import armed, flags

pytestmark = pytest.mark.phase0


async def _health(app) -> dict:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return (await client.get("/health")).json()


# --- 1. assert both configurations in one test ------------------------------
# Self-contained: passes wherever it runs, and fails if either arm changes.
# Good for a fault you can arm and disarm inside a single process.
#
# Note both arms are pinned. Asserting the disarmed behaviour without pinning
# it reads whatever the ambient environment happens to be, so the test breaks
# the first time CI runs the suite with a flag already set.


async def test_health_is_lowercase_unless_the_flag_is_armed():
    with flags(DEMO_HEALTH_BUG=False):
        from app.api import app as clean_app

        assert await _health(clean_app) == {"status": "ok"}

    with flags(DEMO_HEALTH_BUG=True):
        from app.api import app as armed_app

        assert await _health(armed_app) == {"status": "OK"}


# --- 2. one assertion, expected to fail in the armed configuration ----------
# The suite runs once per configuration, and this test states the truth in
# each: green when the fault is disarmed, xfail when it is armed.
#
# `strict=True` matters. Without it the test also passes when the fault is
# fixed, so it stops telling you anything.


@pytest.mark.xfail(
    armed("DEMO_HEALTH_BUG"),
    strict=True,
    reason="DEMO_HEALTH_BUG returns a capitalised status",
)
async def test_health_reports_ok():
    from app.api import app

    assert await _health(app) == {"status": "ok"}
