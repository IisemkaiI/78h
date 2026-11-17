# API

Базовый URL локальной среды: `http://127.0.0.1:8000`.
Префикс версии: `/api/v1`.
Интерактивная документация: `/docs` (Swagger UI), `/openapi.json` (спецификация).

Все ответы — `application/json; charset=utf-8`.

## GET /api/v1/health

Проверка живости процесса. База данных не опрашивается, поэтому эндпоинт
отвечает `200` даже при недоступном PostgreSQL.

**Ответ 200**

```json
{
  "status": "ok",
  "service": "education-platform-api",
  "version": "0.1.0",
  "environment": "local"
}
```

| Поле | Тип | Описание |
| --- | --- | --- |
| `status` | `"ok"` | процесс отвечает |
| `service` | string | идентификатор сервиса |
| `version` | string | версия проекта (`PROJECT_VERSION`) |
| `environment` | string | окружение (`APP_ENV`) |

## GET /api/v1/ready

Проверка готовности принимать трафик. Выполняет реальный `SELECT 1` в PostgreSQL
с таймаутом `DB_READY_TIMEOUT`.

**Ответ 200 — база доступна**

```json
{
  "status": "ready",
  "version": "0.1.0",
  "database": { "status": "available", "detail": null, "latency_ms": 1.84 }
}
```

**Ответ 503 — база недоступна**

```json
{
  "status": "not_ready",
  "version": "0.1.0",
  "database": {
    "status": "unavailable",
    "detail": "ConnectionRefusedError",
    "latency_ms": null
  }
}
```

| Поле | Тип | Описание |
| --- | --- | --- |
| `status` | `"ready"` \| `"not_ready"` | итог проверки зависимостей |
| `database.status` | `"available"` \| `"unavailable"` | результат `SELECT 1` |
| `database.detail` | string \| null | категория ошибки без хоста/логина/пароля |
| `database.latency_ms` | number \| null | время проверки в миллисекундах |

Тело ответа одинаково для `200` и `503` — клиенту не нужно разбирать два формата.

## GET /api/v1/info

Название приложения и версия проекта. Секретов не содержит.

**Ответ 200**

```json
{
  "application": "Education Platform",
  "version": "0.1.0",
  "environment": "local",
  "api_version": "/api/v1"
}
```

## Формат ошибок

Единый конверт для всех ошибок:

```json
{
  "error": {
    "code": "not_found",
    "message": "Not Found",
    "details": null
  }
}
```

| HTTP | `code` | Когда |
| --- | --- | --- |
| 400 | `bad_request` | некорректный запрос |
| 401 | `unauthorized` | нет аутентификации (задел на будущее) |
| 403 | `forbidden` | нет прав (задел на будущее) |
| 404 | `not_found` | маршрут не существует |
| 405 | `method_not_allowed` | метод не поддержан |
| 422 | `validation_error` | не прошла валидация; в `details` — список полей |
| 429 | `too_many_requests` | превышен лимит |
| 500 | `internal_error` | непойманное исключение; подробности только в логе |
| 503 | `service_unavailable` | зависимость недоступна |

Пример ошибки валидации (`details`):

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [{ "location": ["query", "limit"], "message": "Input should be a valid integer", "type": "int_parsing" }]
  }
}
```

Примечание: `/api/v1/ready` при недоступной БД возвращает **тело успешной схемы**
с `status: "not_ready"` и HTTP `503`, а не конверт ошибки — это осознанное
исключение для health-проб.

## CORS

Разрешённые origin'ы задаются переменной `CORS_ORIGINS` (список через запятую).
По умолчанию:

```
http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173
```

`5173` — dev-сервер Vite, `4173` — `npm run preview` (production-сборка).

Запрос с другим `Origin` не получает заголовок `access-control-allow-origin`.
`allow_credentials=true` — задел для будущей аутентификации по cookie.

## Приватность

Через API не передаются: DSN, хост/порт базы, имя пользователя БД, пароли,
переменные окружения, трассировки стека. Проверяется тестами
`tests/test_health.py::test_health_exposes_no_connection_details` и
`tests/test_info.py::test_info_does_not_leak_credentials`.

## Примеры запросов

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe http://127.0.0.1:8000/api/v1/ready
curl.exe http://127.0.0.1:8000/api/v1/info
curl.exe -i -X OPTIONS http://127.0.0.1:8000/api/v1/health `
  -H "Origin: http://localhost:5173" `
  -H "Access-Control-Request-Method: GET"
```

## Версионирование

Все служебные эндпоинты находятся под `/api/v1`. При несовместимых изменениях
вводится `/api/v2`; старый префикс сохраняется на время миграции клиентов.
