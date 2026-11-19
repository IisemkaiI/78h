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
- [Каталог (публичный)](#каталог-публичный)
- [Курсы (авторский API)](#курсы-авторский-api)
- [Схемы данных](#схемы-данных)
- [Формат ошибок](#формат-ошибок)
- [Роли и разрешения](#роли-и-разрешения)
- [CORS](#cors)
- [Приватность](#приватность)
- [Примеры запросов](#примеры-запросов)
- [Версионирование](#версионирование)

## Служебные эндпоинты

### GET /api/v1/health

Проверка живости процесса. База данных не опрашивается, поэтому эндпоинт
отвечает `200` даже при недоступном PostgreSQL.

```json
{
  "status": "ok",
  "service": "education-platform-api",
  "version": "0.3.0",
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
  "version": "0.3.0",
  "database": { "status": "available", "detail": null, "latency_ms": 1.84 }
}
```

**503 — база недоступна**

```json
{
  "status": "not_ready",
  "version": "0.3.0",
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
  "version": "0.3.0",
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

## Каталог (публичный)

Эндпоинты каталога не требуют токена. Неавторизованный посетитель видит только
опубликованные курсы в активных категориях.

### GET /api/v1/catalog/categories

Список активных категорий. Тело ответа — массив `Category`.

```json
[
  {
    "id": "uuid",
    "name": "Программирование",
    "slug": "programming",
    "description": null,
    "is_active": true,
    "created_at": "2026-11-19T14:00:00Z",
    "updated_at": "2026-11-19T14:00:00Z"
  }
]
```

### GET /api/v1/catalog/courses

Список опубликованных курсов с поиском, фильтрами и пагинацией.

| Параметр | Тип | По умолчанию | Описание |
| --- | --- | --- | --- |
| `search` | string | — | `ILIKE` по названию и краткому описанию |
| `category` | string | — | slug категории |
| `level` | string | — | `beginner`, `intermediate`, `advanced` |
| `language` | string | — | точное совпадение, регистронезависимо |
| `sort` | string | `newest` | `newest`, `oldest`, `title` |
| `page` | integer | `1` | номер страницы, ≥1 |
| `page_size` | integer | `12` | размер страницы, 1–48 |

**Ответ 200** — `Paginated<CatalogCourse>`:

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Python с нуля",
      "slug": "python-s-nulya",
      "short_description": "Короткое описание",
      "cover_image_url": null,
      "level": "beginner",
      "language": "ru",
      "category": { "id": "uuid", "name": "Программирование", "slug": "programming" },
      "author": { "id": "uuid", "display_name": "Иван Петров" },
      "published_at": "2026-11-19T14:00:00Z",
      "modules_count": 2,
      "lessons_count": 7,
      "total_duration_minutes": 95
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 12,
  "pages": 1
}
```

Черновики, архивные курсы и курсы из отключённых категорий в выборку не
попадают.

### GET /api/v1/catalog/courses/{slug}

Публичная карточка курса. Ответ — `CatalogCourseDetail`: те же поля, что у
`CatalogCourse`, плюс `description` и `modules` (массив `ModulePreview`).

`ModulePreview` содержит `id`, `title`, `description`, `position` и `lessons`
со списком `LessonPreview` (`id`, `title`, `description`, `position`,
`estimated_duration_minutes`). **Поле `content` намеренно не возвращается**:
материалы уроков станут доступны после записи на курс (Sprint 4).

**Ошибки:** `404 course_not_found` — курс не опубликован, archived, в
неактивной категории или не существует.

## Курсы (авторский API)

Все эндпоинты требуют Bearer-токен и соответствующее разрешение. Автор видит
только свои курсы; администратор (`courses:manage_all`) — любые. Чужой
черновик возвращает `404 course_not_found`.

### GET /api/v1/courses/mine

Свои курсы, включая черновики и архив. Параметры `page` (≥1) и `page_size`
(1–48). Ответ — `Paginated<CourseSummary>`. Требует `courses:read`.

### POST /api/v1/courses

Создаёт черновик. Требует `courses:create`.

**Запрос**

```json
{
  "title": "Python с нуля",
  "short_description": "Короткое описание",
  "description": "Полное описание курса",
  "cover_image_url": null,
  "level": "beginner",
  "language": "ru",
  "category_id": "uuid"
}
```

`author_id`, `status`, `published_at`, `slug` в теле запрещены (`422`). Ответ
`201` — `CourseDetail` со статусом `draft`.

**Ошибки:** `404 category_not_found`, `404 category_inactive`,
`422 validation_error`.

### GET /api/v1/courses/{id}

Курс для редактирования, включая modules/lessons с содержимым. Требует
`courses:read`. Ответ — `CourseDetail`.

### PATCH /api/v1/courses/{id}

Частичное обновление полей курса. Требует `courses:update`. Slug не меняется.
Ответ — обновлённый `CourseDetail`.

### POST /api/v1/courses/{id}/publish

Публикует курс. Требует `courses:publish`. Проверяет наличие заголовка, обоих
описаний, активной категории, уровня, языка, хотя бы одного модуля и урока,
непустых названий и неотрицательной длительности.

**Ответ 200** — `CourseDetail` со статусом `published` и заполненным
`published_at`.

**Ошибка 422 `course_not_ready`:**

```json
{
  "error": {
    "code": "course_not_ready",
    "message": "Course is not ready to be published",
    "details": { "missing": ["modules", "module_1_lesson_1_title"] }
  }
}
```

### POST /api/v1/courses/{id}/unpublish

Возвращает опубликованный или архивный курс в `draft`. Требует
`courses:publish`. `published_at` сохраняется.

### POST /api/v1/courses/{id}/archive

Переводит курс в `archived` (скрыт из каталога, данные сохранены). Требует
`courses:publish`.

### DELETE /api/v1/courses/{id}

Физически удаляет курс вместе с модулями и уроками. Требует `courses:delete`.
Ответ `204`.

### Модули и уроки

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | `/courses/{id}/modules` | Создать модуль: `title`, `description` |
| PATCH | `/courses/{id}/modules/{mid}` | Обновить модуль |
| DELETE | `/courses/{id}/modules/{mid}` | Удалить модуль с уроками |
| POST | `/courses/{id}/modules/reorder` | Перестановка модулей: `ordered_ids` |
| POST | `/courses/{id}/modules/{mid}/lessons` | Создать урок: `title`, `description`, `content`, `estimated_duration_minutes` |
| PATCH | `/courses/{id}/modules/{mid}/lessons/{lid}` | Обновить урок |
| DELETE | `/courses/{id}/modules/{mid}/lessons/{lid}` | Удалить урок |
| POST | `/courses/{id}/modules/{mid}/lessons/reorder` | Перестановка уроков: `ordered_ids` |

Все операции над структурой требуют `courses:update` и проверяют цепочку
`урок → модуль → курс → автор`. Пустое название и отрицательная длительность
отклоняются с `422`. Неверный `ordered_ids` → `422 invalid_order`.

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
| 404 | `course_not_found` | курс/модуль/урок не найден или недоступен этому пользователю |
| 404 | `category_not_found` | категория не существует |
| 404 | `module_not_found`, `lesson_not_found` | элемент структуры не найден в этом курсе |
| 405 | `method_not_allowed` | метод не поддержан |
| 409 | `conflict` | общий конфликт |
| 409 | `email_already_registered` | повторная регистрация |
| 422 | `validation_error` | не прошла валидация; список полей в `details` |
| 422 | `course_not_ready` | публикация: не хватает данных; `details.missing` |
| 422 | `invalid_order` | перестановка: неверный набор/порядок ID |
| 422 | `category_inactive` | выбрана отключённая категория |
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
| `course_author` | `profile:*`, `courses:read`, `courses:create`, `courses:update`, `courses:publish`, `courses:delete`, `learning:participate` (8) |
| `teacher` | `profile:*`, `courses:read`, `learning:participate`, `teaching:manage` |
| `organization_employee` | `profile:*`, `courses:read`, `learning:enroll`, `learning:participate` |
| `organization_manager` | `profile:*`, `courses:read`, `learning:enroll`, `learning:participate`, `organization:view_members`, `organization:manage_members`, `organization:view_reports` |
| `admin` | все 17 разрешений, включая `courses:manage_all` |

Несколько ролей объединяются: пользователь получает объединение разрешений.
`guest` не назначается аккаунтам. Публичного API назначения ролей нет;
`course_author` назначается через CLI `python -m app.cli assign-role`.
Всего в системе 17 уникальных разрешений.

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
Публичная карточка курса не раскрывает `content` уроков, а авторский API —
чужие черновики (404 вместо данных).

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

# публичный каталог (без токена)
Invoke-RestMethod -Uri "$base/catalog/courses?level=beginner&page=1&page_size=12"

# создание черновика (нужна роль course_author)
$draft = Invoke-RestMethod -Method Post -Uri "$base/courses" -Headers $headers `
  -ContentType "application/json" -Body (@{
    title = "Python с нуля"
    short_description = "Короткое описание"
    description = "Полное описание курса"
    cover_image_url = $null
    level = "beginner"
    language = "ru"
    category_id = "<uuid категории>"
  } | ConvertTo-Json)

# публикация
Invoke-RestMethod -Method Post -Uri "$base/courses/$($draft.id)/publish" -Headers $headers
```

## Версионирование

Все эндпоинты находятся под `/api/v1`. При несовместимых изменениях вводится
`/api/v2`; старый префикс сохраняется на время миграции клиентов.
