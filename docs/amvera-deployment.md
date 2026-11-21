# Развёртывание на Amvera

Демо-стенд «Вектор» на [Amvera Cloud](https://amvera.ru): API и веб-клиент
работают в одном контейнере, база данных — управляемый PostgreSQL.

## Почему один контейнер

Amvera запускает один контейнер на проект и не поддерживает `docker-compose`.
Поэтому фронтенд собирается внутри образа
(`deploy/amvera/Dockerfile`), а FastAPI раздаёт готовый SPA вместе с API:

- один домен — нет CORS и проблем с cookie;
- `VITE_API_BASE_URL` пустой, фронтенд ходит на относительный `/api/v1`;
- миграции Alembic применяются при старте (`deploy/amvera/entrypoint.sh`).

## Что нужно создать в Amvera

1. **Приложение** (Docker), регион Москва.
2. Подключить GitHub-репозиторий `IisemkaiI/78h`, ветка `master`.
   Amvera собирает проект по `amvera.yaml` (Dockerfile:
   `deploy/amvera/Dockerfile`, порт `8000`, хранилище `/data`).
3. **PostgreSQL** (managed, одна реплика). Запомнить имя БД, пользователя и
   пароль. Внутренний хост для записи — `cnpg-<имя-проекта>-rw`, порт `5432`
   (точное значение — во вкладке «Домены» кластера).
4. В проекте приложения включить бесплатный домен во вкладке «Домены».

## Переменные приложения

Добавить во вкладку «Переменные» (пароли — как секреты):

| Переменная | Значение |
| --- | --- |
| `PROJECT_NAME` | `Vector` |
| `PROJECT_VERSION` | `0.8.0` |
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `LOG_LEVEL` | `INFO` |
| `API_V1_PREFIX` | `/api/v1` |
| `FRONTEND_DIST_DIR` | `/srv/frontend` |
| `CERTIFICATES_STORAGE_DIR` | `/data/certificates` |
| `PUBLIC_FRONTEND_URL` | `https://<домен>` |
| `CORS_ORIGINS` | `https://<домен>` |
| `POSTGRES_HOST` | `cnpg-<имя-проекта>-rw` |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_USER` | пользователь БД |
| `POSTGRES_PASSWORD` | пароль БД (секрет) |
| `POSTGRES_DB` | имя БД |
| `JWT_SECRET` | случайная строка ≥ 32 символов (секрет) |
| `JWT_ISSUER` | `education-platform` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `DB_POOL_SIZE` | `2` |
| `DB_MAX_OVERFLOW` | `2` |

`JWT_SECRET` можно сгенерировать так:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

После изменения переменных Amvera перезапускает контейнер.

## Проверка

- `GET https://<домен>/api/v1/health` — `{"status": "ok", ...}`;
- `GET https://<домен>/` — веб-клиент;
- прямой заход на `https://<домен>/courses/<slug>` — SPA, не 404;
- регистрация, вход, каталог, запись на курс, урок;
- `/api/v1/docs` — OpenAPI.

## Ограничения демо-стенда

- Celery worker/beat не запускаются: автоматическая пометка просроченных
  корпоративных назначений не работает. Остальные функции не зависят от Celery.
- Redis не требуется.
- PDF-сертификаты хранятся в `/data/certificates` (постоянное хранилище Amvera).
- Для мобильного клиента (Capacitor) позже понадобится добавить
  `https://localhost` в `CORS_ORIGINS`.

## Обновление

Пуш в `master` запускает автоматическую пересборку. Миграции применяются
контейнером при старте. Если схема несовместима — сначала сделайте бэкап
кластера PostgreSQL во вкладке «Бэкапы».
