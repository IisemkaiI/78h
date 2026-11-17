# PostgreSQL init scripts (reserved)

Sprint 0 does not need init scripts: the project database and its owner are created
by the official image from `POSTGRES_DB` / `POSTGRES_USER`.

Use this directory later for `*.sql` / `*.sh` files that must run once, on an empty
volume. To enable it, mount it in `docker-compose.yml`:

```yaml
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ../infrastructure/docker/postgres:/docker-entrypoint-initdb.d:ro
```

Note: scripts in `/docker-entrypoint-initdb.d` are executed only when the data
directory is empty. Changing them requires removing the volume
(`docker compose down -v`) — which destroys data.

Schema changes belong in Alembic migrations (Sprint 1), not here.
