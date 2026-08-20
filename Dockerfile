FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /srv
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml --extra dev

COPY app ./app
COPY tests ./tests
COPY migrations ./migrations

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
