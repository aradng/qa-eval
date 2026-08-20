#!/usr/bin/env bash
# One-shot setup. Brings up Postgres, Redis, Redpanda and the service,
# creates the schema, and runs the smoke tests.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> building and starting the stack"
docker compose up -d --build --wait

echo "==> creating the local virtualenv"
if ! command -v uv >/dev/null; then
    echo "uv not found. install it: https://docs.astral.sh/uv/" >&2
    exit 1
fi
uv venv --python 3.13
uv pip install -q -e ".[dev]"

echo "==> creating the database schema"
.venv/bin/python -m app.main

echo "==> smoke tests"
.venv/bin/pytest -q -m phase0

cat <<'DONE'

Ready.

  service      http://localhost:58000/docs
  postgres     postgresql://qa:qa@localhost:55432/qa
  redis        redis://localhost:56379/0
  kafka        localhost:59092
  registry     http://localhost:58081

  tests        .venv/bin/pytest -m phase0
  ci matrix    ./bin/ci
  arm a fault  MIRROR_AFTER_COMMIT=true .venv/bin/pytest ...
  logs         docker compose logs -f app
  reset        docker compose down -v && ./setup.sh
DONE
