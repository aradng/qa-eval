# Migrations

Not applied by default. Apply one with:

```bash
docker compose exec -T postgres psql -U qa -d qa < migrations/M1_add_broker.sql
```

Reset to a clean database with `docker compose down -v && ./setup.sh`.
