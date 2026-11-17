# База данных

## 1. Что подготовлено в Sprint 0

Доменных таблиц пока нет — по условиям спринта нельзя создавать таблицы
образовательных модулей. Подготовлено только подключение:

- PostgreSQL 17 в отдельном контейнере (`docker-compose.yml`);
- постоянный том `education-platform-postgres-data`;
- отдельная база проекта `education_platform` и отдельный пользователь `edu_platform`;
- асинхронный движок SQLAlchemy 2 с пулом соединений;
- фабрика сессий и FastAPI-зависимость `get_session` (пока не используется);
- проверка доступности БД через `/api/v1/ready` (реальный `SELECT 1`).

SQLite и другие заменители PostgreSQL не используются.

## 2. Параметры подключения

Все значения читаются из корневого `.env` (`app/core/config.py`, класс `Settings`).

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `POSTGRES_HOST` | хост, видимый backend-процессу | `127.0.0.1` |
| `POSTGRES_PORT` | порт, опубликованный контейнером | `5432` |
| `POSTGRES_USER` | пользователь БД | `edu_platform` |
| `POSTGRES_PASSWORD` | пароль (секрет) | — (обязателен) |
| `POSTGRES_DB` | имя базы проекта | `education_platform` |

DSN собирается в `Settings.database_dsn`:

```
postgresql+asyncpg://<user>:<password>@<host>:<port>/<db>
```

DSN нигде не логируется целиком и никогда не возвращается через API.
`POSTGRES_PASSWORD` хранится в `pydantic.SecretStr`, поэтому не попадает в
`repr`/`model_dump`.

## 3. Docker Compose

```yaml
services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB} -h 127.0.0.1"]
```

Особенности:

- пароли не записаны в compose-файл, только ссылки на переменные `.env`;
- `${VAR:?сообщение}` заставляет Compose упасть с понятной ошибкой, если
  переменная не задана;
- `healthcheck` использует `pg_isready`, поэтому `docker compose ps` показывает
  `healthy` только когда БД реально принимает подключения;
- данные лежат в томе `education-platform-postgres-data`, а `PGDATA` указывает на
  подкаталог `pgdata` — это защищает от проблем с правами на смонтированном томе.

## 4. Подключение из приложения

`app/core/database.py`:

```python
engine = create_async_engine(
    settings.database_dsn,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,          # DB_POOL_SIZE = 5
    max_overflow=settings.db_max_overflow,    # DB_MAX_OVERFLOW = 10
    pool_timeout=settings.db_pool_timeout,    # DB_POOL_TIMEOUT = 30
    connect_args={"timeout": settings.db_connect_timeout},   # DB_CONNECT_TIMEOUT = 5
)
```

- `pool_pre_ping=True` — перед выдачей соединения из пула оно проверяется, что
  убирает «протухшие» соединения после перезапуска контейнера;
- `SessionFactory` (`async_sessionmaker`) — единая точка создания сессий;
- `get_session()` — FastAPI-зависимость для будущих модулей:

```python
@router.get("/example")
async def example(session: Annotated[AsyncSession, Depends(get_session)]):
    ...
```

Закрытие пула выполняется в lifespan приложения (`dispose_engine()`).

## 5. Проверка готовности

`ping_database()` выполняет `SELECT 1` с ограничением по времени
(`DB_READY_TIMEOUT`, по умолчанию 3 с):

- успех → `/api/v1/ready` отвечает `200`, `"status": "ready"`,
  `database.status = "available"`, `latency_ms` — измеренная задержка;
- ошибка или таймаут → `503`, `"status": "not_ready"`,
  `database.status = "unavailable"`, `detail` — короткая категория проблемы
  (например, `ConnectionRefusedError`) без хостов, логинов и паролей.

Наблюдаемое поведение на машине без Docker (реальная проверка):

```
GET /api/v1/ready -> 503
{"status":"not_ready","version":"0.1.0",
 "database":{"status":"unavailable","detail":"ConnectionRefusedError","latency_ms":null}}
```

## 6. Как проверить подключение

```powershell
cd D:\education-platform
docker compose up -d postgres
docker compose ps                     # STATUS = healthy

curl.exe http://127.0.0.1:8000/api/v1/health   # 200
curl.exe http://127.0.0.1:8000/api/v1/ready    # 200, status=ready

cd backend
.\.venv\Scripts\python.exe -m pytest -m integration
```

Проверка постоянного хранения:

```powershell
docker compose exec postgres psql -U edu_platform -d education_platform -c "CREATE TABLE storage_probe (id int);"
docker compose restart postgres
docker compose exec postgres psql -U edu_platform -d education_platform -c "\dt"
# таблица storage_probe должна остаться; после проверки её можно удалить
```

## 7. Миграции

Alembic в Sprint 0 не подключён (нет моделей и нет задач на схему). Планируется
первым шагом Sprint 1: `alembic init`, `env.py` на async-движке, `alembic upgrade head`
в документации запуска. До этого схема базы пустая.

## 8. Диагностика

| Симптом | Причина | Решение |
| --- | --- | --- |
| `/ready` → `503`, `detail: "ConnectionRefusedError"` | контейнер не запущен или порт занят | `docker compose up -d postgres`, проверить `docker compose ps` |
| `/ready` → `503`, `detail: "TimeoutError"` | контейнер стартует | подождать `healthy`, повторить запрос |
| `password authentication failed` в логах backend | `.env` изменён после создания контейнера | пересоздать: `docker compose down -v` + `up -d` (удалит данные) |
| порт 5432 занят локальным PostgreSQL | конфликт портов | изменить `POSTGRES_PORT` в `.env` (например, `55432`) |
| `docker compose` ругается на отсутствующие переменные | нет `.env` | `Copy-Item .env.example .env` |
