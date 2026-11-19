# Архитектура

## 1. Общая модель

Проект строится как **модульный монолит**.

Один репозиторий, один backend-процесс, одна база данных. Внутри backend код
делится на изолированные доменные модули, каждый из которых владеет своей
моделью данных, сервисами и (при необходимости) переиспользуемыми зависимостями.
Модули общаются через явные Python-интерфейсы, а не через прямые запросы к чужим
таблицам.

Такой подход выбран осознанно:

- на старте нет распределённых транзакций, сети и дублирования моделей;
- отдельные модули можно позже вынести в отдельные сервисы без переписывания;
- одна команда может разрабатывать проект без инфраструктурных накладных расходов.

Микросервисы, Redis, Celery и APScheduler не вводятся — это преждевременное
усложнение для текущего этапа.

## 2. Слои

```
┌──────────────────────────────────────────────┐
│ Browser: React + TypeScript + Vite           │
│  pages/ → auth/ (состояние) → services/      │
│  Router: /, /login, /register, /profile,     │
│          /catalog, /catalog/:slug,           │
│          /author, /author/new, /author/...   │
└───────────────────────┬──────────────────────┘
                        │ HTTP/JSON, Bearer JWT, CORS
┌───────────────────────▼──────────────────────┐
│ FastAPI (backend/app)                        │
│  api/v1/     — HTTP-слой: system, auth,      │
│                users, catalog, courses       │
│  modules/    — users, auth, courses          │
│  core/       — config, database, errors,     │
│                security (Argon2, JWT)        │
│  cli.py      — назначение ролей               │
│  workers/    — фоновые задачи (пока пусто)   │
└───────────────────────┬──────────────────────┘
                        │ SQLAlchemy 2 async + asyncpg
┌───────────────────────▼──────────────────────┐
│ PostgreSQL 17 (Docker Compose, volume)       │
│  users, roles, permissions, user_roles,      │
│  role_permissions,                           │
│  categories, courses, course_modules, lessons│
└──────────────────────────────────────────────┘
```

Правила зависимостей:

- `api/` знает про `modules/` и `core/`, но не наоборот;
- `modules/` используют `core/` (сессии БД, настройки, безопасность) и не
  зависят от `api/`;
- `core/` не импортирует ничего из `api/` или `modules/`;
- фронтенд обращается к backend только через `src/services/`, компоненты не
  вызывают `fetch` напрямую;
- проверки доступа выполняются только на backend, frontend повторяет их для UX.

## 3. Backend

| Компонент | Ответственность |
| --- | --- |
| `app/main.py` | фабрика `create_app()`, lifespan, CORS, регистрация роутеров и обработчиков ошибок |
| `app/core/config.py` | типизированные настройки из `.env`, сборка DSN, JWT-конфигурация, валидация секрета |
| `app/core/database.py` | async-движок, `Base` с naming convention, фабрика сессий, `get_session`, `ping_database` |
| `app/core/errors.py` | единый конверт ошибок, `ApiError`, обработчики исключений |
| `app/core/security.py` | Argon2id, политика паролей, нормализация email, выпуск/проверка JWT |
| `app/api/v1/router.py` | сборка версионированного API |
| `app/api/v1/endpoints/*` | HTTP-эндпоинты (`system`, `auth`, `users`, `catalog`, `courses`) |
| `app/api/deps.py` | `SessionDep` — внедрение `AsyncSession` |
| `app/modules/users/` | модели, RBAC-коды, репозиторий, сервис, Pydantic-схемы |
| `app/modules/auth/` | `AuthService` (проверка пароля), зависимости `get_current_user`, `require_roles`, `require_permissions` |
| `app/modules/courses/` | домен курсов: `models/`, `schemas/`, `repositories/`, `services/`, `constants.py` |
| `app/cli.py` | безопасное назначение/снятие ролей (`assign-role`, `remove-role`, `list-roles`, `list-users`) |

Версионирование: все эндпоинты живут под `/api/v1`. При несовместимых изменениях
появляется `/api/v2`, старый префикс сохраняется на период миграции.

### Слои внутри модуля

```
api/v1/endpoints/auth.py     HTTP: разбор запроса, вызов сервиса, ответ
        ↓
modules/auth/service.py      бизнес-правило: credentials → User
modules/users/service.py     бизнес-правило: регистрация, профиль
        ↓
modules/users/repository.py  SQL: выборки, вставки, eager-loading
        ↓
modules/users/models.py      ORM-модели и связи
```

Схемы Pydantic (`modules/users/schemas.py`) описывают контракт и отклоняют
неизвестные поля (`extra="forbid"`), поэтому клиент не может передать `roles`,
`is_active`, `permissions` или `email` в запрос на изменение профиля.

### Обработка ошибок

Все ошибки возвращаются в едином формате:

```json
{ "error": { "code": "not_found", "message": "Not Found", "details": null } }
```

- `StarletteHTTPException` → код из маппинга (`not_found`, `method_not_allowed`, ...);
- `ApiError` → собственный стабильный `code` (`invalid_credentials`,
  `email_already_registered`, `token_expired`, ...) и `details`;
- `RequestValidationError` → `422`, `code: "validation_error"`, список полей в `details`;
- непойманное исключение → `500`, `code: "internal_error"`, трассировка пишется
  только в серверный лог.

Никакие DSN, хосты, пользователи, пароли и хеши в ответы не попадают.

### Liveness и readiness

- `/health` — «процесс жив»; не касается базы, поэтому остаётся `200` при упавшей БД.
- `/ready` — «можно принимать трафик»; выполняет реальный `SELECT 1` с таймаутом и
  возвращает `503` при недоступности PostgreSQL.

## 4. Пользователи и RBAC

### Модель

`User` содержит только используемые поля: UUID, уникальный нормализованный email,
Argon2id-хеш, отображаемое имя, флаг активности и временные метки. Пароль в
открытом виде нигде не сохраняется.

Роли не являются Enum-колонкой. Используются четыре таблицы:

```
users ──< user_roles >── roles ──< role_permissions >── permissions
```

- пользователь может иметь несколько ролей;
- роль может содержать несколько разрешений;
- разрешения пользователя — объединение разрешений всех его ролей;
- `guest` засеяна для полноты, но не назначается аккаунтам: неавторизованный
  запрос просто не имеет пользователя.

### Проверка доступа

Переиспользуемые зависимости в `modules/auth/dependencies.py`:

| Зависимость | Семантика |
| --- | --- |
| `get_current_user` / `CurrentUser` | Bearer-токен → пользователь; 401 для отсутствующего/невалидного/просроченного токена, 403 для деактивированного аккаунта |
| `require_roles(*codes)` | хотя бы одна из перечисленных ролей (any-of) |
| `require_permissions(*codes)` | все перечисленные разрешения (all-of) |

Эндпоинты профиля защищены `require_permissions("profile:read")` и
`require_permissions("profile:update")`. Неавторизованный пользователь получает
`401`, пользователь без нужной роли/разрешения — `403`.

При регистрации сервис сам находит роль `user` в БД и назначает её. Публичного
эндпоинта назначения ролей нет; назначение привилегированных ролей выполняется
внутренними средствами и появится в админ-панели позже.

### Пароли и JWT

- Argon2id: `time_cost=3`, `memory_cost=65536 KiB`, `parallelism=4`, соль 16 байт,
  хеш 32 байта (RFC 9106, low-memory профиль).
- Политика: 10–128 символов, минимум одна буква и одна цифра, без пробелов по
  краям, deny-list распространённых паролей, запрет совпадения с email.
- При входе с неизвестным email выполняется проверка фиктивного хеша, чтобы
  снизить разницу во времени ответа (защита от user enumeration).
- JWT HS256, `sub` = UUID, `iss`, `iat`, `exp`, `jti`, `type="access"`.
  Секрет читается только из `.env` и проверяется на минимальную длину.
- Refresh-токены и серверный отзыв не реализованы в Sprint 1; это ограничение
  зафиксировано в README и `docs/api.md`.

## 5. Каталог и курсы

### Домен `courses`

Модуль `app/modules/courses/` разделён на слои по тому же принципу, что и
`users`:

```
api/v1/endpoints/catalog.py   публичные/read-only запросы (без токена)
api/v1/endpoints/courses.py   авторский API (требует разрешений)
        ↓
modules/courses/services/     CatalogService, CategoryService,
                              CourseService, StructureService;
                              проверка владельца, транслитерация slug,
                              валидация публикации
        ↓
modules/courses/repositories/ SQL: выборки каталога, CRUD курса/структуры
        ↓
modules/courses/models/       Category, Course, CourseModule, Lesson
```

Схемы (`schemas/`) описывают контракт и запрещают лишние поля (`extra="forbid"`),
поэтому клиент не может передать `author_id`, `status`, `published_at` или
`slug`. Статус и уровень хранятся как `VARCHAR` с CHECK-ограничениями
(`status_values`, `level_values`), а не как PostgreSQL ENUM — это упрощает
расширение значений без изменения типа колонки.

### Сущности и связи

```
categories 1──< courses >──1 users (author)
                  │
                  └──1──< course_modules >──1──< lessons
```

- `Category`: id, name, slug (уникальный), description, is_active, timestamps;
  8 категорий засеяны миграцией `0004_seed_courses`, публичны только активные.
- `Course`: заголовок, slug (уникальный, неизменяемый), описания, обложка
  (URL), level, language, status (`draft`/`published`/`archived`), author_id,
  category_id, published_at, timestamps. Новый курс всегда создаётся как
  `draft`; `published_at` выставляется при первой публикации и сохраняется при
  повторных.
- `CourseModule` и `Lesson`: позиция (`position`) начинается с 1, перестановка и
  удаление выполняются транзакционно (двухфазная схема с отрицательными
  позициями при
  reorder, `ON DELETE CASCADE` + перенумерация при delete). Содержимое урока —
  только Markdown-текст, загрузка файлов/видео не предусмотрена.

### Права и изоляция

| Действие | Разрешение |
| --- | --- |
| Просмотр каталога и публичной карточки | без токена (`guest`) |
| Список/чтение своих курсов | `courses:read` |
| Создание | `courses:create` |
| Редактирование, модули, уроки | `courses:update` |
| Публикация / возврат в черновик / архивация | `courses:publish` |
| Удаление | `courses:delete` |
| Обход проверки владельца (админ) | `courses:manage_all` |

Обычный автор видит только свои курсы; доступ к чужому черновику или архиву
возвращает `404 course_not_found` (не `403`) — это не раскрывает существование
чужого курса. Администратор с `courses:manage_all` работает с любым курсом.
Frontend повторяет проверки через `RequirePermission` только для UX;
решающая проверка всегда на backend.

### Публикация

`POST /courses/{id}/publish` проверяет: название, оба описания, активную
категорию, уровень, язык, хотя бы один модуль, хотя бы один урок, непустые
названия и неотрицательную длительность. При ошибке возвращается `422
course_not_ready` с `details.missing` — список символических полей, который
frontend превращает в читаемый чеклист. Slug при публикации не меняется,
поэтому ссылки остаются валидными.

### Ключевые отклонения от ТЗ

- Разрешения курсов используют множественное число (`courses:*`).
- Публичный API живёт под `/catalog/...`, авторский — под `/courses/...`.
- `status`/`level` — `VARCHAR` + CHECK, не ENUM.
- Назначение `course_author` — через CLI, без публичного эндпоинта (Sprint 8).

## 6. Frontend

| Каталог | Назначение |
| --- | --- |
| `src/app/` | `App` (Router + Provider), `AppLayout` (шапка, навигация) |
| `src/auth/` | `AuthProvider` (состояние сессии), `ProtectedRoute`, `RequirePermission` |
| `src/pages/` | `Home`, `Login`, `Register`, `Profile`, `Catalog`, `CourseDetail`, `AuthorCourses`, `NewCourse`, `CourseEditor`, `NotFound` |
| `src/components/` | `ConnectionStatus`, `components/course/*` (карточка, формы, редактор структуры) |
| `src/hooks/` | состояние и побочные эффекты (`useBackendStatus`) |
| `src/services/` | `apiClient`, `authService`, `tokenStorage`, `systemService`, `catalogService`, `courseService` |
| `src/types/` | контракты API, зеркало backend-схем (включая курсы) |
| `src/utils/` | валидация форм, русские сообщения об ошибках, подписи, `courseErrors` |
| `src/styles/` | `variables.css`, `global.css`, `ui.css`, `catalog.css`, `editor.css` |

`RequirePermission` — только UX-защита: скрывает ссылки и перенаправляет, но
не заменяет backend-проверки. `ApiError` несёт `code` и `details`, благодаря
чему `courseErrors.ts` показывает читаемый список недостающих полей при
неудачной публикации.

### Состояние аутентификации

- После успешного входа/регистрации токен и `expires_at` сохраняются в
  `localStorage` (`education-platform.auth.v1`).
- При старте `AuthProvider` читает сессию, отбрасывает истёкшую и проверяет
  токен через `GET /auth/me`; пока проверка идёт, статус `loading`.
- `ProtectedRoute` при статусе `anonymous` перенаправляет на `/login`, сохраняя
  исходный путь в `location.state.from`.
- `signOut()` очищает `localStorage` и состояние, затем вызывает
  `POST /auth/logout` (best effort). Redirect выполняет страница/шапка.
- Токен не пишется в консоль и не логируется; пароль не сохраняется нигде.

### Сеть

- базовый URL из `VITE_API_BASE_URL`;
- каждый запрос ограничен таймаутом (`AbortController`);
- тела запросов сериализуются в JSON, заголовок `Authorization` добавляется
  только при наличии токена;
- ошибки нормализуются в `ApiError` с типом (`network`, `timeout`, `http`,
  `invalid_response`), HTTP-кодом и стабильным `code` backend'а;
- UI различает состояния загрузки, успеха и ошибки; коды backend'а
  переводятся в понятные русские сообщения.

## 7. Данные и миграции

Схема создаётся исключительно Alembic-ревизиями:

- `0001_users_rbac` — таблицы пользователей и RBAC, индексы, внешние ключи;
- `0002_seed_rbac` — системные роли, разрешения и матрица `role_permissions`;
- `0003_courses` — `categories`, `courses`, `course_modules`, `lessons`,
  CHECK-ограничения и индексы;
- `0004_seed_courses` — 8 категорий и расширение матрицы разрешений до 17.

Seed-ревизии идемпотентны (`ON CONFLICT DO NOTHING`). `alembic/env.py`
использует async-движок и DSN из `Settings`; переменная
`ALEMBIC_DATABASE_URL` позволяет тестам мигрировать отдельную базу. В рабочем
коде `create_all()` не вызывается. Подробности — [`database.md`](database.md).

## 8. Инфраструктура

- только PostgreSQL в Docker (`docker-compose.yml` в корне);
- backend и frontend запускаются локально, что ускоряет цикл разработки;
- данные БД — в именованном томе, что переживает перезапуск контейнера;
- секреты — только через `.env`, который не попадает в Git.

## 9. Что осознанно не сделано в Sprint 2

Refresh-токены и серверный отзыв JWT, подтверждение email, восстановление
пароля, rate limiting, административная панель и API управления ролями,
загрузка файлов и видео, запись на курс и прогресс, тесты, сертификаты,
корпоративный кабинет, уведомления, Redis, Celery, APScheduler.

## 10. Направление развития

1. ~~Alembic и первые доменные модели.~~ (Sprint 1)
2. ~~Пользователи, роли, аутентификация и авторизация.~~ (Sprint 1)
3. ~~Каталог и конструктор курсов.~~ (Sprint 2)
4. Процесс обучения и прогресс.
5. Тестирование и практические задания.
6. Сертификация.
7. Корпоративный кабинет и админ-панель.
8. Уведомления, затем фоновые задачи (Redis + Celery / APScheduler).

Последовательность и критерии выхода по этапам — в
[`development-plan.md`](development-plan.md).
