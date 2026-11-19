# База данных

## 1. Состояние после Sprint 1

PostgreSQL 17 работает в Docker Compose. Схема создаётся и версионируется
Alembic-миграциями; `create_all()` в приложении не используется.

Таблицы Sprint 1:

| Таблица | Назначение |
| --- | --- |
| `users` | зарегистрированные аккаунты |
| `roles` | системные роли (`guest`, `user`, `course_author`, ...) |
| `permissions` | атомарные разрешения (`profile:read`, `courses:create`, ...) |
| `user_roles` | связь многие-ко-многим пользователь ↔ роль |
| `role_permissions` | связь многие-ко-многим роль ↔ разрешение |
| `alembic_version` | текущая ревизия схемы |

Таблиц курсов, обучения, тестирования, сертификации и организаций пока нет.

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
`POSTGRES_PASSWORD` и `JWT_SECRET` хранятся в `pydantic.SecretStr`, поэтому не
попадают в `repr`/`model_dump`.

## 3. Схема

### `users`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK, генерируется приложением |
| `email` | `varchar(320)` | NOT NULL, UNIQUE (`uq_users_email`), индекс `ix_users_email` |
| `password_hash` | `varchar(255)` | NOT NULL, Argon2id-хеш |
| `display_name` | `varchar(120)` | NOT NULL |
| `is_active` | `boolean` | NOT NULL, default `true` |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |
| `updated_at` | `timestamptz` | NOT NULL, default `now()`, обновляется приложением |

Правила:

- email нормализуется (trim + lowercase) и в схеме, и в `@validates` модели;
- пароль хранится только как Argon2id-хеш (`$argon2id$...`);
- хеш никогда не входит в Pydantic-схемы ответов;
- лишних полей (телефон, аватар, подтверждение email и т.п.) нет.

### `roles`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK |
| `code` | `varchar(50)` | NOT NULL, UNIQUE (`uq_roles_code`), индекс `ix_roles_code` |
| `name` | `varchar(100)` | NOT NULL |
| `description` | `varchar(255)` | NULL |

### `permissions`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK |
| `code` | `varchar(100)` | NOT NULL, UNIQUE (`uq_permissions_code`), индекс `ix_permissions_code` |
| `description` | `varchar(255)` | NULL |

### Связи

```
user_roles(user_id → users.id ON DELETE CASCADE,
           role_id → roles.id ON DELETE CASCADE,
           PK(user_id, role_id))

role_permissions(role_id → roles.id ON DELETE CASCADE,
                 permission_id → permissions.id ON DELETE CASCADE,
                 PK(role_id, permission_id))
```

Связи поддерживают несколько ролей у пользователя и несколько разрешений у роли.
Разрешения пользователя вычисляются как объединение разрешений всех ролей.

## 4. Начальные данные RBAC

Ревизия `0002_seed_rbac` создаёт данные идемпотентно
(`ON CONFLICT DO NOTHING`), не удаляя ничего существующего.

| Роль | Кол-во разрешений |
| --- | --- |
| `guest` | 0 |
| `user` | 5 |
| `course_author` | 7 |
| `teacher` | 5 |
| `organization_employee` | 5 |
| `organization_manager` | 8 |
| `admin` | 15 |

Разрешения сгруппированы по будущим модулям: `profile:*`, `courses:*`,
`learning:*`, `teaching:*`, `organization:*`, `admin:*`. Матрица ролей
(какая роль получает какие разрешения) зафиксирована в миграции, чтобы
исторические ревизии оставались воспроизводимыми.

`guest` — не аккаунт, а обозначение неавторизованного посетителя. Роль
существует для полноты модели, не имеет разрешений и никогда не назначается
записи в `users`.

## 5. Миграции

Файлы:

```
backend/alembic.ini
backend/alembic/env.py                 async-движок, DSN из Settings
backend/alembic/versions/0001_users_rbac.py
backend/alembic/versions/0002_seed_rbac.py
```

Команды (из `backend/`):

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe downgrade -1
.\.venv\Scripts\alembic.exe revision --autogenerate -m "describe change"
```

Особенности:

- `env.py` берёт DSN из `Settings`, поэтому креденшелы не хранятся в `alembic.ini`;
- `ALEMBIC_DATABASE_URL` (необязательная переменная) переопределяет DSN — так
  integration-тесты мигрируют отдельную базу, не затрагивая рабочую;
- `compare_type=True` включает сравнение типов при autogenerate;
- тест `test_orm_metadata_matches_migrations` проверяет отсутствие расхождений
  между моделями SQLAlchemy и фактической схемой.

## 6. Docker Compose

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

- пароли не записаны в compose-файл, только ссылки на переменные `.env`;
- `healthcheck` показывает `healthy` только когда БД принимает подключения;
- данные лежат в томе `education-platform-postgres-data`, подкаталог `PGDATA`
  защищает от проблем с правами на смонтированном томе.

Проверено: `docker compose ps` → `Up ... (healthy)`, PostgreSQL 17.12.

## 7. Подключение из приложения

`app/core/database.py`:

```python
engine = create_async_engine(
    settings.database_dsn,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,          # DB_POOL_SIZE = 5
    max_overflow=settings.db_max_overflow,    # DB_MAX_OVERFLOW = 10
    pool_timeout=settings.db_pool_timeout,    # DB_POOL_TIMEOUT = 30
    connect_args={"timeout": settings.db_connect_timeout},
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
```

- `Base` использует naming convention, поэтому имена PK/FK/UNIQUE/индексов
  детерминированы и совпадают в моделях и миграциях;
- `pool_pre_ping=True` убирает «протухшие» соединения после перезапуска;
- `get_session()` — FastAPI-зависимость; модули получают её через `SessionDep`;
- закрытие пула выполняется в lifespan (`dispose_engine()`).

Eager-loading ролей и разрешений (`selectinload`) исключает неявные SQL-запросы
из async-контекста.

## 8. Проверка готовности

`ping_database()` выполняет `SELECT 1` с ограничением `DB_READY_TIMEOUT` (3 с):

- успех → `/api/v1/ready` отвечает `200`, `"status": "ready"`,
  `database.status = "available"`, `latency_ms` — измеренная задержка;
- ошибка/таймаут → `503`, `"status": "not_ready"`,
  `database.status = "unavailable"`, `detail` — короткая категория проблемы
  (например, `ConnectionRefusedError`) без хостов, логинов и паролей.

## 9. Тестовая база

Integration-тесты используют отдельную базу `education_platform_test`
(переопределяется `TEST_POSTGRES_DB`). `tests/integration/conftest.py`:

1. создаёт базу, если её нет (через asyncpg и служебную БД `postgres`);
2. применяет `alembic upgrade head` с `ALEMBIC_DATABASE_URL`;
3. создаёт async-движок с `NullPool`;
4. очищает `user_roles` и `users` перед каждым тестом (`TRUNCATE ... CASCADE`),
   сохраняя засеянные роли и разрешения.

SQLite не используется: тесты проверяют настоящее поведение PostgreSQL.

## 10. Проверка вручную

```powershell
cd D:\education-platform
docker compose up -d postgres
docker compose ps                     # healthy

cd backend
.\.venv\Scripts\alembic.exe upgrade head

docker exec education-platform-postgres psql -U edu_platform -d education_platform -c "\dt"
docker exec education-platform-postgres psql -U edu_platform -d education_platform `
  -c "select r.code, count(rp.permission_id) from roles r left join role_permissions rp on rp.role_id=r.id group by r.code order by r.code;"
```

Сохранение данных после перезапуска backend:

1. зарегистрировать пользователя через API;
2. остановить и снова запустить uvicorn;
3. выполнить `POST /api/v1/auth/login` с теми же данными — вход должен пройти;
4. проверить запись в `users` через `psql`.

Сохранение после перезапуска контейнера проверяется `docker compose restart postgres`.

## 11. Диагностика

| Симптом | Причина | Решение |
| --- | --- | --- |
| `/ready` → `503`, `detail: "ConnectionRefusedError"` | контейнер не запущен | `docker compose up -d postgres` |
| `/ready` → `503`, `detail: "TimeoutError"` | контейнер стартует | дождаться `healthy` |
| `password authentication failed` | `.env` изменён после создания контейнера | пересоздать том (удалит данные) или вернуть пароль |
| `relation "users" does not exist` | миграции не применены | `alembic upgrade head` |
| `Role 'user' is missing from the database` (500) | seed-миграция не применена | `alembic upgrade head` |
| `JWT_SECRET must be set...` при старте | нет секрета в `.env` | сгенерировать и добавить `JWT_SECRET` |
| порт 5432 занят | локальный PostgreSQL | изменить `POSTGRES_PORT` |
| тесты идут в рабочую базу | не задан `TEST_POSTGRES_DB`/конфиг conftest | проверить `tests/integration/conftest.py` |
