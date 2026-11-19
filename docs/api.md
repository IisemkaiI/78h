# API

Базовый URL локальной среды: `http://127.0.0.1:8000`.
Префикс версии: `/api/v1`.
Интерактивная документация: `/docs` (Swagger UI), `/openapi.json` (спецификация).

Все ответы — `application/json; charset=utf-8`. Защищённые эндпоинты ожидают
заголовок `Authorization: Bearer <access_token>`.

## Содержание

- [Служебные эндпоинты](#служебные-эндпоинты)
- [Аутентификация](#аутентификация)
- [Профиль пользователя](#профиль-пользователя)
- [Схемы данных](#схемы-данных)
- [Формат ошибок](#формат-ошибок)
- [Роли и разрешения](#роли-и-разрешения)
- [CORS](#cors)
- [Приватность](#приватность)
- [Версионирование](#версионирование)

## Служебные эндпоинты

### GET /api/v1/health

Проверка живости процесса. База данных не опрашивается, поэтому эндпоинт
отвечает `200` даже при недоступном PostgreSQL.

```json
{
  "status": "ok",
  "service": "education-platform-api",
  "version": "0.2.0",
  "environment": "local"
}
```

### GET /api/v1/ready

Проверка готовности принимать трафик. Выполняет реальный `SELECT 1` в PostgreSQL
с таймаутом `DB_READY_TIMEOUT`.

**200 — база доступна**

```json
{
  "status": "ready",
  "version": "0.2.0",
  "database": { "status": "available", "detail": null, "latency_ms": 1.84 }
}
```

**503 — база недоступна**

```json
{
  "status": "not_ready",
  "version": "0.2.0",
  "database": {
    "status": "unavailable",
    "detail": "ConnectionRefusedError",
    "latency_ms": null
  }
}
```

Тело ответа одинаково для `200` и `503`. Это осознанное исключение из общего
конверта ошибок для health-проб.

### GET /api/v1/info

```json
{
  "application": "Education Platform",
  "version": "0.2.0",
  "environment": "local",
  "api_version": "/api/v1"
}
```

## Аутентификация

### POST /api/v1/auth/register

Создаёт аккаунт, назначает **только** базовую роль `user` и сразу выдаёт access
token (авто-вход). Привилегированные роли через этот эндпоинт получить нельзя:
схема отклоняет любые поля, кроме `email`, `password`, `display_name`.

**Запрос**

```json
{
  "email": "ivan.petrov@example.com",
  "password": "Str0ngPassw0rd!",
  "display_name": "Иван Петров"
}
```

| Поле | Правила |
| --- | --- |
| `email` | валидный email; нормализуется (trim + lowercase); уникален |
| `password` | 10–128 символов, минимум одна буква и одна цифра, без пробелов по краям, не из deny-list, не равен email |
| `display_name` | 2–120 символов, схлопывание повторных пробелов, минимум одна буква/цифра |

**Ответ 201**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "8ed03f0a-42f8-44c4-85f4-ae85b4f84be8",
    "email": "ivan.petrov@example.com",
    "display_name": "Иван Петров",
    "is_active": true,
    "created_at": "2026-11-19T15:17:07.123456Z",
    "updated_at": "2026-11-19T15:17:07.123456Z",
    "roles": [{ "code": "user", "name": "Пользователь" }],
    "permissions": [
      "courses:read",
      "learning:enroll",
      "learning:participate",
      "profile:read",
      "profile:update"
    ]
  }
}
```

**Ошибки**

| HTTP | `code` | Когда |
| --- | --- | --- |
| 409 | `email_already_registered` | email уже занят (регистр не важен) |
| 422 | `validation_error` | невалидный email, слабый пароль, лишние поля (`roles`, `is_active`, ...) |
| 500 | `rbac_not_initialized` | не применена seed-миграция ролей |

### POST /api/v1/auth/login

Проверяет email, пароль и активность аккаунта. Возвращает ту же схему, что и
регистрация. Для несуществующего email и неверного пароля ответ одинаковый,
чтобы не раскрывать наличие аккаунта.

**Запрос**

```json
{ "email": "ivan.petrov@example.com", "password": "Str0ngPassw0rd!" }
```

**Ответ 200** — `TokenResponse` (см. выше).

**Ошибки**

| HTTP | `code` | Когда |
| --- | --- | --- |
| 401 | `invalid_credentials` | неизвестный email или неверный пароль |
| 403 | `account_inactive` | аккаунт деактивирован |
| 422 | `validation_error` | отсутствует/некорректен email или пароль |

### POST /api/v1/auth/logout

Требует Bearer-токен. Возвращает `204 No Content` без тела.

JWT — stateless: сервер не может отозвать уже выданный токен до истечения срока.
Эндпоинт существует для явности операции; клиент обязан удалить токен сам.
Серверный отзыв (denylist/refresh-токены) запланирован на будущее.

**Ошибки:** `401 not_authenticated`.

### GET /api/v1/auth/me

Возвращает профиль текущего пользователя, включая роли и разрешения.

**Ответ 200** — объект `UserProfile` (см. [Схемы данных](#схемы-данных)).

**Ошибки:** `401 not_authenticated`, `401 invalid_token`, `401 token_expired`,
`403 account_inactive`.

### GET /api/v1/auth/me/permissions

Диагностический эндпоинт: роли и объединённые разрешения текущего пользователя.

```json
{
  "roles": ["course_author", "user"],
  "permissions": ["courses:create", "courses:publish", "...", "profile:update"]
}
```

## Профиль пользователя

### GET /api/v1/users/me

Свой профиль. Требует разрешение `profile:read` (есть у роли `user`).

**Ответ 200** — объект `UserProfile`.

**Ошибки:** `401 not_authenticated`, `403 insufficient_permissions`.

### PATCH /api/v1/users/me

Изменяет только отображаемое имя. UUID, email, роли, разрешения и `is_active`
изменить нельзя: неизвестные поля отклоняются с `422`.

**Запрос**

```json
{ "display_name": "Иван П." }
```

**Ответ 200** — обновлённый `UserProfile`.

**Ошибки**

| HTTP | `code` | Когда |
| --- | --- | --- |
| 401 | `not_authenticated` | нет/просрочен токен |
| 403 | `insufficient_permissions` | у пользователя нет `profile:update` |
| 422 | `validation_error` | имя короче 2 или длиннее 120 символов; переданы `email`, `roles`, `is_active`, `permissions` |

## Схемы данных

### UserProfile

```json
{
  "id": "uuid",
  "email": "string",
  "display_name": "string",
  "is_active": true,
  "created_at": "2026-11-19T15:17:07.123456Z",
  "updated_at": "2026-11-19T15:17:07.123456Z",
  "roles": [{ "code": "user", "name": "Пользователь" }],
  "permissions": ["profile:read", "profile:update"]
}
```

`password_hash` никогда не входит в ответ.

### TokenResponse

```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "...": "UserProfile" }
}
```

JWT payload: `sub` (UUID пользователя), `type` (`access`), `iss`, `iat`, `exp`,
`jti`. Алгоритм HS256; секрет и время жизни задаются в `.env`.

## Формат ошибок

Единый конверт для всех ошибок, кроме `/ready`:

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
| 401 | `unauthorized` | общая ошибка аутентификации |
| 401 | `not_authenticated` | заголовок `Authorization` отсутствует |
| 401 | `invalid_token` | подпись/формат/issuer/тип токена неверны, пользователь не найден |
| 401 | `token_expired` | истёк `exp` |
| 401 | `invalid_credentials` | неверный email или пароль |
| 403 | `forbidden` | общая ошибка доступа |
| 403 | `account_inactive` | аккаунт деактивирован |
| 403 | `insufficient_roles` | нет ни одной из требуемых ролей |
| 403 | `insufficient_permissions` | нет одного или нескольких разрешений; список в `details.missing` |
| 404 | `not_found` | маршрут не существует |
| 405 | `method_not_allowed` | метод не поддержан |
| 409 | `conflict` | общий конфликт |
| 409 | `email_already_registered` | повторная регистрация |
| 422 | `validation_error` | не прошла валидация; список полей в `details` |
| 429 | `too_many_requests` | превышен лимит (задел) |
| 500 | `internal_error` | непойманное исключение; подробности только в логе |
| 500 | `rbac_not_initialized` | отсутствуют системные роли |
| 503 | `service_unavailable` | зависимость недоступна |

Пример ошибки валидации:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {
        "location": ["body", "password"],
        "message": "Value error, Password must contain at least one digit.",
        "type": "value_error"
      }
    ]
  }
}
```

Ответы `401` содержат `WWW-Authenticate: Bearer`.

## Роли и разрешения

| Роль | Разрешения (коды) |
| --- | --- |
| `guest` | — |
| `user` | `profile:read`, `profile:update`, `courses:read`, `learning:enroll`, `learning:participate` |
| `course_author` | `profile:*`, `courses:read`, `courses:create`, `courses:update`, `courses:publish`, `learning:participate` |
| `teacher` | `profile:*`, `courses:read`, `learning:participate`, `teaching:manage` |
| `organization_employee` | `profile:*`, `courses:read`, `learning:enroll`, `learning:participate` |
| `organization_manager` | `profile:*`, `courses:read`, `learning:enroll`, `learning:participate`, `organization:view_members`, `organization:manage_members`, `organization:view_reports` |
| `admin` | все 15 разрешений |

Несколько ролей объединяются: пользователь получает объединение разрешений.
`guest` не назначается аккаунтам. Публичного API назначения ролей нет.

## CORS

Разрешённые origin'ы задаются переменной `CORS_ORIGINS` (список через запятую).
По умолчанию:

```
http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173
```

`5173` — dev-сервер Vite, `4173` — `npm run preview`. Запрос с другим `Origin`
не получает заголовок `access-control-allow-origin`.

## Приватность

Через API не передаются: DSN, хост/порт базы, имя пользователя БД, пароли,
хеши паролей, JWT-секрет, переменные окружения, трассировки стека. Это
проверяется тестами `test_health_exposes_no_connection_details`,
`test_info_does_not_leak_credentials` и
`tests/integration/test_auth_api.py::test_register_response_never_exposes_password_material`.

## Примеры запросов

```powershell
$base = "http://127.0.0.1:8000/api/v1"

# регистрация
$reg = Invoke-RestMethod -Method Post -Uri "$base/auth/register" -ContentType "application/json" -Body (@{
  email = "user@example.com"; password = "Str0ngPassw0rd!"; display_name = "Тестовый Пользователь"
} | ConvertTo-Json)

$headers = @{ Authorization = "Bearer $($reg.access_token)" }

# текущий пользователь
Invoke-RestMethod -Uri "$base/auth/me" -Headers $headers

# профиль
Invoke-RestMethod -Uri "$base/users/me" -Headers $headers

# изменение имени
Invoke-RestMethod -Method Patch -Uri "$base/users/me" -Headers $headers `
  -ContentType "application/json" -Body (@{ display_name = "Новое Имя" } | ConvertTo-Json)

# выход
Invoke-WebRequest -Method Post -Uri "$base/auth/logout" -Headers $headers -UseBasicParsing
```

## Версионирование

Все эндпоинты находятся под `/api/v1`. При несовместимых изменениях вводится
`/api/v2`; старый префикс сохраняется на время миграции клиентов.
