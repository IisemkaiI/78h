# Демонстрационный запуск и подготовка к серверу

## Локальная разработка

Обычный локальный стек оставлен прежним: PostgreSQL в Docker, backend через
Uvicorn и frontend через Vite.

```powershell
cd D:\education-platform
docker compose up -d postgres
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Во втором окне:

```powershell
cd D:\education-platform\frontend
npm.cmd ci
npm.cmd run dev
```

## Linux-сервер с Docker Compose

Для минимального развёртывания подготовлен `docker-compose.server.yml`: web
(Nginx + собранный React SPA), FastAPI, PostgreSQL, Redis, Celery Worker и
Celery Beat. База и Redis остаются внутри Docker-сети; сертификаты сохраняются
в приватном Docker volume. API выполняет `alembic upgrade head` при старте.

На Linux VDS с Docker Compose v2:

1. Передайте исходники на сервер и скопируйте `.env.example` в `.env`.
2. Задайте длинные случайные `POSTGRES_PASSWORD`, `JWT_SECRET` (не менее 32
   символов) и URL-safe `REDIS_PASSWORD` (буквы, цифры, `_`, `-`). Не загружайте
   `.env` в репозиторий.
3. Задайте `PRODUCTION_CORS_ORIGINS=https://ваш-домен` и
   `PUBLIC_FRONTEND_URL=https://ваш-домен`.
4. Запустите:

```bash
docker compose -f docker-compose.server.yml --env-file .env up --build -d
docker compose -f docker-compose.server.yml --env-file .env ps
docker compose -f docker-compose.server.yml --env-file .env logs -f api worker scheduler
```

Веб-интерфейс слушает `APP_HTTP_PORT` (по умолчанию `8080`). Перед ним следует
настроить HTTPS reverse proxy или TLS на хосте. DNS A/AAAA должен вести на VDS;
откройте внешние порты 80/443 только для web/proxy. Не публикуйте PostgreSQL,
Redis или backend API напрямую.

Проверка очереди: после запуска можно отправить реальное задание в worker и
посмотреть task id в ответе и лог `Marked N corporate assignments overdue`:

```bash
docker compose -f docker-compose.server.yml --env-file .env exec worker \
  celery -A app.workers.celery_app:app call app.workers.tasks.mark_overdue_assignments
```

Beat запускает ту же задачу каждые 15 минут. При первом запуске ожидаемые
`N=0` нормальны, если нет просроченных принятых курсов. Задача идемпотентна;
ошибки логируются и повторяются до трёх раз. Логи контейнеров являются
операционным журналом; отдельная таблица аудита фоновых задач пока не ведётся.

Celery официально не поддерживает Windows, поэтому worker/beat в этом проекте
предназначены для Linux-контейнеров или Linux-сервера, а не для запуска как
нативного Windows-процесса ([документация Celery](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)).

## Эксплуатационные требования

- Используйте Linux VDS с Docker Engine/Compose, доменом и TLS.
- Делайте регулярные резервные копии PostgreSQL и проверяйте восстановление.
- Сохраняйте Docker volumes `server_postgres_data`, `server_redis_data` и
  `server_certificates` при обновлении.
- Обновляйте приложение из проверенной версии; проверяйте логи API/worker и
  доступность `/api/v1/health`.
- Compose конфигурация — минимальный шаблон для демонстрации, не HA-схема;
  Redis не имеет репликации, а сертификаты хранятся локально в volume.
