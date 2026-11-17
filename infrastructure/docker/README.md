# Infrastructure / Docker

Sprint 0 uses exactly **one** containerised service: PostgreSQL.

The Compose file lives in the project root (`docker-compose.yml`) because it is
part of the top-level developer workflow and must be able to read the root
`.env` file automatically.

```
docker compose up -d postgres      # start the database
docker compose ps                  # container + health status
docker compose logs -f postgres    # follow logs
docker compose down                # stop (data is kept in the volume)
```

## Contents of this directory

| Path | Purpose |
| --- | --- |
| `postgres/` | Reserved for future PostgreSQL init scripts (`*.sql`, mounted at `/docker-entrypoint-initdb.d`). Empty in Sprint 0 — the project database is created from `POSTGRES_DB`. |

## Data persistence

Data is stored in the named Docker volume `education-platform-postgres-data`
(declared at the bottom of `docker-compose.yml`). `docker compose down` keeps
the volume; only `docker compose down -v` deletes the data.

## Not included on purpose

Redis, Celery, APScheduler and a backend container are out of scope for
Sprint 0. The FastAPI backend runs locally with `uvicorn` so that the database
dependency can be verified independently.
