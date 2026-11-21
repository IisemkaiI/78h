#ужас https://uceeeeeee-semka.msk1.amvera.tech/catalog

Многофункциональная образовательная LMS-платформа. Репозиторий содержит
фундамент проекта (**Sprint 0**), базовую систему пользователей (**Sprint 1**),
каталог и конструктор курсов (**Sprint 2**), процесс обучения (**Sprint 4**),
тесты с практическими заданиями (**Sprint 5**) и сертификаты (**Sprint 6**):
React-клиент, FastAPI-бэкенд, PostgreSQL, Alembic-миграции, регистрацию, вход
по JWT, личный профиль, реляционную ролевую модель (RBAC), публичный каталог
курсов, редактор курсов для авторов, запись на курсы, три состояния урока,
прогресс и журнал обучения, тесты с историей попыток, практические задания с
проверкой преподавателем, назначение преподавателей на курс, неизменяемые
снимки сертификатов, приватные PDF и публичную проверку подлинности.

Текущее состояние: Sprint 7 (уведомления) и Sprint 8 (корпоративный кабинет)
реализованы. Версия сдаваемой сборки — `0.8.0`. Для краткой инструкции демонстрационного запуска и Linux Compose
развёртывания смотрите [docs/demo-and-deployment.md](docs/demo-and-deployment.md).
Административная панель и одноуровневые подразделения описаны там же и в
[документации API](docs/api.md).

## Исторический статус Sprint 6 (снимок версии 0.6.0)

| Критерий | Статус |
| --- | --- |
| PostgreSQL 17 в Docker Compose | проверено (healthy) |
| Alembic-миграции схемы | применены, head `0008_certificates` |
| Системные роли и разрешения | 7 ролей, 34 разрешения |
| Регистрация с базовой ролью `user` | проверено тестами |
| Вход по email/паролю, JWT access token | проверено тестами |
| Личный профиль (`GET/PATCH /users/me`) | проверено тестами |
| RBAC-зависимости ролей и разрешений | проверено тестами |
| Защита от самостоятельного назначения ролей | проверено тестами |
| Категории курсов (8 засеянных, только активные публичны) | проверено |
| Публичный каталог: поиск, фильтры, сортировка, пагинация | проверено тестами |
| Публичная карточка курса (без содержимого уроков) | проверено |
| Автор: создание, редактирование, публикация, архивация | проверено тестами |
| Модули и уроки с порядком, перестановкой и удалением | проверено тестами |
| Запись только на опубликованный курс в активной категории | проверено тестами |
| Автор не может записаться на свой курс | проверено тестами |
| Отмена и повторная запись сохраняют прогресс и историю | проверено тестами |
| Три состояния урока и согласованный процент прогресса | проверено тестами |
| Материалы урока только для активной записи | проверено тестами |
| Пересчёт прогресса при добавлении/удалении урока | проверено тестами |
| Удаление урока сохраняет историю; удаление курса с записями → 409 | проверено тестами |
| Администратор читает записи и опубликованные курсы | проверено тестами |
| Тесты, версии попыток и автоматическая проверка ответов | unit + PostgreSQL integration |
| Практические задания, версии отправок и отзывы преподавателей | PostgreSQL integration + ручной UI |
| Обязательные проверки в общем прогрессе курса | API + ручной UI: 0/2 → 1/2 → 2/2; с уроком 100% |
| Назначение преподавателя и просмотр очереди работ | ручной UI |
| Сертификат — только после выполнения прогресса | общий `ProgressService` + PostgreSQL integration |
| PDF: кириллица, A4 landscape, приватная выдача | ReportLab + Noto Sans, PDF unit/API integration |
| Идемпотентность, повторная запись, параллельная выдача | unique FK + `FOR UPDATE`, PostgreSQL integration |
| Публичная проверка без утечки внутренних данных | PostgreSQL API integration |
| Светлая/тёмная тема с сохранением предпочтения | браузер и production build |
| Frontend Sprint 5: авторинг, прохождение, проверка и предпросмотр черновика | ручной UI, ошибок консоли нет |
| Backend-тесты (unit + PostgreSQL) | 22 unit + 105 integration, все зелёные |
| TypeScript typecheck и production build | проверено; предупреждение Vite о чанке 545 kB |
| Проект | версия `0.6.0` |

Подробности проверок и ограничения — в конце README и в
[`docs/development-plan.md`](docs/development-plan.md).

## Технологии

**Frontend:** React 19, TypeScript 5.9, Vite 7, React Router 7.
**Backend:** Python 3.14, FastAPI, Uvicorn, SQLAlchemy 2 (async), asyncpg, Pydantic 2, pydantic-settings.
**Аутентификация:** Argon2id (`argon2-cffi`), JWT HS256 (`PyJWT`).
**Миграции:** Alembic (async-движок).
**База данных:** PostgreSQL 17 (официальный образ `postgres:17-alpine`).
**Инфраструктура:** Docker Compose, Git.
**Тесты:** pytest, pytest-asyncio, httpx; реальный PostgreSQL для integration-тестов.

Redis, Celery и APScheduler не подключаются до отдельного этапа (Sprint 9).

## Структура каталогов

```
education-platform/
├── frontend/                     React + TypeScript + Vite
│   ├── public/                   статические файлы
│   ├── src/
│   │   ├── app/                  App, AppLayout, стили оболочки
│   │   ├── assets/               изображения/иконки
│   │   ├── auth/                 AuthProvider, ProtectedRoute, RequirePermission
│   │   ├── components/           ConnectionStatus, components/course/*,
│   │   │                         components/learning/* (прогресс, Markdown)
│   │   ├── hooks/                useBackendStatus
│   │   ├── pages/                Home, Login, Register, Profile, Catalog,
│   │   │                         CourseDetail, MyLearning, LearnCourse,
│   │   │                         AuthorCourses, AuthorCoursePreview,
│   │   │                         NewCourse, CourseEditor
│   │   ├── services/             apiClient, authService, tokenStorage,
│   │   │                         systemService, catalogService, courseService,
│   │   │                         learningService
│   │   ├── styles/               дизайн-токены, global.css, ui.css, catalog.css,
│   │   │                         editor.css, learning.css
│   │   ├── types/                контракты API
│   │   ├── utils/                валидация, сообщения об ошибках, подписи,
│   │   │                         courseErrors, learningErrors
│   │   ├── main.tsx
│   │   └── vite-env.d.ts
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── backend/                      FastAPI
│   ├── alembic/                  env.py и ревизии 0001–0005
│   │   └── versions/
│   │       ├── 0001_users_rbac.py
│   │       ├── 0002_seed_rbac.py
│   │       ├── 0003_courses.py    схемы категорий, курсов, модулей, уроков
│   │       ├── 0004_seed_courses.py  8 категорий + расширение RBAC
│   │       ├── 0005_learning.py   записи, прогресс, журнал + RBAC обучения
│   │       ├── 0006_assessments.py тесты, отправки, проверки, преподаватели
│   │       ├── 0007_assessment_lesson_retention.py история удалённых уроков
│   │       └── 0008_certificates.py сертификаты и разрешения
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py           SessionDep
│   │   │   └── v1/               router, endpoints (system, auth, users,
│   │   │                         catalog, courses, learning)
│   │   ├── core/                 config, database, errors, security
│   │   ├── modules/
│   │   │   ├── auth/             AuthService, get_current_user, require_roles/permissions
│   │   │   ├── users/            модели, RBAC-коды, репозиторий, сервис, схемы
│   │   │   ├── courses/          models/, schemas/, repositories/, services/, constants
│   │   │   └── learning/         записи, прогресс, журнал, доступ к материалам
│   │   ├── cli.py                безопасное назначение ролей (assign-role и др.)
│   │   ├── workers/              будущие фоновые задачи (пусто)
│   │   └── main.py
│   ├── tests/                    unit-тесты
│   │   └── integration/          тесты на реальном PostgreSQL
│   ├── alembic.ini
│   ├── pytest.ini
│   ├── requirements.txt
│   └── requirements-dev.txt
├── infrastructure/
│   ├── docker/                   пояснения к контейнерам
│   └── scripts/                  check-environment.ps1
├── docs/
│   ├── architecture.md
│   ├── frontend-design-system.md
│   ├── database.md
│   ├── api.md
│   └── development-plan.md
├── docker-compose.yml            PostgreSQL
├── .env.example                  шаблон конфигурации (копируется в .env)
├── .gitignore
└── README.md
```

## Требования к окружению

| Компонент | Версия (проверено на этой машине) |
| --- | --- |
| ОС | Windows 10 |
| Python | 3.14.5 (`py` launcher) |
| Node.js / npm | 26.13.1 / 11.20.0 |
| Git | 2.56.0 |
| Docker Desktop | 29.9.3, WSL2, PostgreSQL 17.12 в контейнере |

Автоматическая проверка окружения:

```powershell
powershell -ExecutionPolicy Bypass -File infrastructure/scripts/check-environment.ps1
```

Скрипт ничего не устанавливает и не меняет. Код возврата `1` означает, что часть
проверок недоступна (например, Docker не запущен).

## Переменные окружения

### Корневой `.env`

Используется Docker Compose, бэкендом и Alembic — единственный источник
параметров подключения и секретов.

```powershell
Copy-Item .env.example .env
# затем задайте POSTGRES_PASSWORD и JWT_SECRET
```

| Переменная | Назначение | Пример |
| --- | --- | --- |
| `PROJECT_NAME` | Название приложения | `Education Platform` |
| `PROJECT_VERSION` | Версия проекта | `0.6.0` |
| `APP_ENV` | Окружение: `local`/`test`/`staging`/`production` | `local` |
| `DEBUG` | SQL echo и подробные логи | `false` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `API_V1_PREFIX` | Префикс версионированного API | `/api/v1` |
| `BACKEND_HOST`, `BACKEND_PORT` | Адрес, на котором публикуется backend | `127.0.0.1`, `8000` |
| `CORS_ORIGINS` | Разрешённые origin'ы фронтенда (через запятую) | `http://localhost:5173,...` |
| `POSTGRES_HOST` | Хост БД с точки зрения backend | `127.0.0.1` |
| `POSTGRES_PORT` | Порт, публикуемый контейнером | `5432` |
| `POSTGRES_USER` | Пользователь БД | `edu_platform` |
| `POSTGRES_PASSWORD` | Пароль БД (секрет) | — |
| `POSTGRES_DB` | Имя базы проекта | `education_platform` |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT` | Пул соединений | `5`, `10`, `30` |
| `DB_CONNECT_TIMEOUT` | Таймаут установки соединения, с | `5` |
| `DB_READY_TIMEOUT` | Таймаут проверки готовности, с | `3` |
| `JWT_SECRET` | Ключ подписи JWT (секрет, ≥32 символов) | — |
| `JWT_ALGORITHM` | Алгоритм подписи | `HS256` |
| `JWT_ISSUER` | Значение `iss` в токене | `education-platform` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни access token, мин | `60` |

Сгенерировать секрет JWT:

```powershell
backend\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Приложение не запустится, если `JWT_SECRET` короче 32 символов или содержит
placeholder `change_me`. Секреты в коде отсутствуют.

### `frontend/.env`

```powershell
Copy-Item frontend/.env.example frontend/.env
```

| Переменная | Назначение | Пример |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Базовый URL backend для браузера | `http://127.0.0.1:8000` |

Файлы `.env` находятся в `.gitignore`. В репозиторий попадают только `.env.example`.

## Запуск PostgreSQL через Docker

```powershell
cd D:\education-platform
docker compose up -d postgres
docker compose ps                  # STATUS должен стать healthy
```

Если `docker` не найден в PowerShell, добавьте его в PATH текущей сессии:

```powershell
$env:Path = "C:\Program Files\Docker\Docker\resources\bin;" + $env:Path
```

Остановка без потери данных:

```powershell
docker compose down
```

Полное удаление данных (том `education-platform-postgres-data`):

```powershell
docker compose down -v
```

## Миграции базы данных

Все команды выполняются из `backend/`:

```powershell
cd D:\education-platform\backend

# применить все миграции
.\.venv\Scripts\alembic.exe upgrade head

# текущая ревизия
.\.venv\Scripts\alembic.exe current

# откатить последнюю ревизию
.\.venv\Scripts\alembic.exe downgrade -1

# новая ревизия по изменениям моделей (после правки моделей)
.\.venv\Scripts\alembic.exe revision --autogenerate -m "describe change"
```

`create_all()` в рабочем приложении не используется: схема создаётся только
миграциями. Ревизии `0002_seed_rbac`, `0004_seed_courses` и `0005_learning`
идемпотентно создают системные роли, разрешения, категории и RBAC обучения
(`ON CONFLICT DO NOTHING`) и не удаляют существующие данные. Текущая ревизия —
`0008_certificates`.

## Запуск Backend

```powershell
cd D:\education-platform\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Без активации окружения:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe http://127.0.0.1:8000/api/v1/ready
curl.exe http://127.0.0.1:8000/api/v1/info
```

Документация API: <http://127.0.0.1:8000/docs>

## Запуск Frontend

```powershell
cd D:\education-platform\frontend
npm install
npm run dev
```

Откройте <http://127.0.0.1:5173>.

Сборка и проверка типов:

```powershell
npm run typecheck
npm run build
npm run preview
```

Страницы:

| Маршрут | Назначение | Доступ |
| --- | --- | --- |
| `/` | Стартовая страница и статус backend | всем |
| `/login` | Вход | неавторизованным |
| `/register` | Регистрация | неавторизованным |
| `/profile` | Личный профиль | только авторизованным |
| `/catalog` | Публичный каталог курсов | всем |
| `/catalog/:slug` | Публичная страница курса | всем (только опубликованные) |
| `/author` | Мои курсы | `courses:read` |
| `/author/new` | Создание курса | `courses:create` |
| `/author/courses/:id` | Редактор курса | `courses:update` |

> Если PowerShell выдаёт `npm.ps1 cannot be loaded because running scripts is
> disabled`, используйте `npm.cmd` вместо `npm`.

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/v1/health` | Процесс жив, БД не затрагивается |
| GET | `/api/v1/ready` | Готовность: `SELECT 1` в PostgreSQL |
| GET | `/api/v1/info` | Название приложения и версия |
| POST | `/api/v1/auth/register` | Регистрация, выдаёт access token |
| POST | `/api/v1/auth/login` | Вход, выдаёт access token |
| POST | `/api/v1/auth/logout` | Клиентский выход (`204`) |
| GET | `/api/v1/auth/me` | Текущий пользователь, роли, разрешения |
| GET | `/api/v1/auth/me/permissions` | Роли и разрешения текущего пользователя |
| GET | `/api/v1/users/me` | Свой профиль (требует `profile:read`) |
| PATCH | `/api/v1/users/me` | Изменение имени (требует `profile:update`) |
| GET | `/api/v1/catalog/categories` | Список активных категорий |
| GET | `/api/v1/catalog/courses` | Каталог: поиск, фильтры, пагинация |
| GET | `/api/v1/catalog/courses/{slug}` | Публичная карточка курса |
| GET | `/api/v1/courses/mine` | Свои курсы, включая черновики |
| POST | `/api/v1/courses` | Создание черновика |
| GET | `/api/v1/courses/{id}` | Курс для редактирования |
| PATCH | `/api/v1/courses/{id}` | Обновление полей курса |
| POST | `/api/v1/courses/{id}/publish` | Публикация (проверка структуры) |
| POST | `/api/v1/courses/{id}/unpublish` | Возврат в черновики |
| POST | `/api/v1/courses/{id}/archive` | Архивация |
| DELETE | `/api/v1/courses/{id}` | Удаление курса |
| POST/GET/PATCH/DELETE | `/api/v1/courses/{id}/modules...` | Управление модулями |
| POST/PATCH/DELETE | `/api/v1/courses/{id}/modules/{mid}/lessons...` | Управление уроками |
| POST | `/api/v1/learning/enrollments` | Запись на курс / возобновление |
| GET | `/api/v1/learning/enrollments/mine` | Свои записи с прогрессом |
| GET | `/api/v1/learning/enrollments/by-course/{id}` | Статус записи по курсу |
| GET/DELETE | `/api/v1/learning/enrollments/{id}` | Чтение / отмена записи |
| GET | `/api/v1/learning/enrollments/{id}/progress` | Прогресс курса |
| GET | `/api/v1/learning/enrollments/{id}/history` | Журнал и удалённые уроки |
| PUT | `/api/v1/learning/enrollments/{id}/lessons/{lid}/progress` | Состояние урока |
| GET | `/api/v1/learning/courses/{slug}` | Программа для обучающегося |
| GET | `/api/v1/learning/courses/{slug}/lessons/{lid}` | Markdown-контент урока |
| POST/PATCH | `/api/v1/assessments/quizzes...` | Авторинг и публикация тестов |
| POST | `/api/v1/assessments/quizzes/{id}/attempts` | Начать попытку теста |
| PUT/POST | `/api/v1/assessments/assignments/{id}/submission/...` | Черновик и отправка практики |
| GET/POST/DELETE | `/api/v1/assessments/courses/{id}/instructors...` | Назначения преподавателей |
| GET/POST | `/api/v1/assessments/teaching`, `/submissions/...` | Очередь и проверка работ |

Полное описание схем, кодов ошибок и примеров — в [`docs/api.md`](docs/api.md).
Визуальная система, адаптивные правила и принципы взаимодействия frontend описаны в [`docs/frontend-design-system.md`](docs/frontend-design-system.md).

## Роли и разрешения

Роли хранятся в реляционных таблицах (`roles`, `permissions`, `user_roles`,
`role_permissions`), а не в Enum-поле пользователя. Один пользователь может
иметь несколько ролей; его разрешения — объединение разрешений всех ролей.

| Роль | Назначение |
| --- | --- |
| `guest` | Неавторизованный посетитель; аккаунтам не назначается |
| `user` | Базовая роль каждого зарегистрированного аккаунта |
| `course_author` | Создание и публикация курсов |
| `teacher` | Ведение обучения и проверка заданий |
| `organization_employee` | Обучение в рамках организации |
| `organization_manager` | Управление сотрудниками и отчётами |
| `admin` | Полный доступ к платформе |

При регистрации сервер назначает только роль `user`. Публичного API назначения
ролей нет; поля `roles`, `permissions`, `is_active` в формах отклоняются с `422`.
Роль `course_author` назначается только из CLI (см. ниже). Коды разрешений
курсов используют множественное число: `courses:read`, `courses:create`,
`courses:update`, `courses:publish`, `courses:delete`, `courses:manage_all` —
это осознанное отклонение от единственного числа в ТЗ. Обучение использует
`enrollments:create`, `enrollments:read_own`, `enrollments:cancel_own`,
`enrollments:manage_all`, `progress:read_own`, `progress:update_own`,
`progress:manage_all`. Всего 24 разрешения; `*:manage_all` есть только у
`admin`.

### Назначение роли `course_author`

```powershell
cd D:\education-platform\backend
.\.venv\Scripts\python.exe -m app.cli assign-role --email author@example.com --role course_author
.\.venv\Scripts\python.exe -m app.cli list-roles --email author@example.com
.\.venv\Scripts\python.exe -m app.cli remove-role --email author@example.com --role course_author
```

Команда отказывается назначать `guest`; роль `user` уже выдаётся при регистрации.
Публичного эндпоинта назначения ролей нет (Sprint 8).

## Тесты

```powershell
cd D:\education-platform\backend

# unit-тесты, БД не требуется
.\.venv\Scripts\python.exe -m pytest

# integration-тесты на реальном PostgreSQL (Docker должен быть запущен)
.\.venv\Scripts\python.exe -m pytest -m integration
```

Integration-тесты используют отдельную базу `education_platform_test` (переопределяется
переменной `TEST_POSTGRES_DB`). База создаётся и мигрируется автоматически, между
тестами очищаются `learning_events`, `lesson_progress`, `enrollments`, `lessons`,
`course_modules`, `courses`, `user_roles`, `users`. SQLite не используется.

Фактический прогон Sprint 4 (2026-11-20, сохранён как исторический результат):

```
pytest                     -> 11 passed, 102 deselected
pytest -m integration      -> 102 passed, 11 deselected
npm run typecheck          -> ok
npm run build              -> ok (предупреждение Vite о чанке >500 kB)
alembic upgrade/downgrade/upgrade -> ok
```

Фактический прогон Sprint 6 (2026-11-20):

```
pytest                     -> 25 passed, 110 deselected
pytest -m integration      -> 110 passed, 25 deselected (PostgreSQL)
alembic current/heads      -> 0008_certificates (head)
alembic check              -> No new upgrade operations detected
npm run typecheck          -> ok
npm run build              -> ok (Vite warning: JS chunk 556 kB)
```

## Безопасность

- Пароли хранятся только как Argon2id-хеши (RFC 9106 параметры: `time_cost=3`,
  `memory_cost=65536`, `parallelism=4`); API никогда не возвращает хеш.
- Политика пароля: 10–128 символов, буква и цифра, без пробелов по краям,
  запрет распространённых паролей и пароля, совпадающего с email.
- Email нормализуется (trim + lowercase) и уникален.
- JWT: HS256, секрет только из окружения, ограниченное время жизни, проверка
  подписи, срока действия, issuer и типа токена.
- Все проверки ролей и разрешений выполняются на backend через переиспользуемые
  зависимости FastAPI.
- Автор может читать и изменять только свои курсы; доступ к чужому черновику
  возвращает `404 course_not_found` (не `403`). Администратор обходит проверку
  владельца через `courses:manage_all`.
- Запись и прогресс принадлежат пользователю: чужая запись возвращает `404`
  даже при известном UUID. Материалы урока доступны только активной записи на
  опубликованный курс; снятый с публикации курс закрывает доступ, сохраняя
  запись и историю.
- Клиент не может задать `author_id`, `status`, `published_at` или `slug`:
  Pydantic-схемы отклоняют эти поля с `422`, значения вычисляет сервер.
- Frontend не является средством защиты: он лишь скрывает элементы и
  перенаправляет неавторизованных пользователей.

### Ограничения аутентификации

- Refresh-токены не реализованы: только короткоживущий access token.
- Отзыв выданных JWT не поддерживается. `POST /auth/logout` удаляет токен на
  клиенте, но сервер не ведёт denylist, поэтому перехваченный токен остаётся
  валидным до истечения срока. Это задокументированное ограничение Sprint 1.
- Нет подтверждения email, восстановления пароля и rate limiting для
  `/auth/login`.

## Git

История Sprint 0 не переписывалась. Sprint 1, Sprint 2 и Sprint 4 оформлены
логическими коммитами (backend, tests, frontend, docs). `.gitignore` исключает
`node_modules`, виртуальные окружения Python, `__pycache__`, `.env`, логи, кеши,
сборки и временные файлы. Секреты и `.env` в репозиторий не попадают.

## Известные ограничения Sprint 4

- JWT нельзя отозвать до истечения срока (нет denylist/refresh-токенов).
- Нет административного API и панели управления ролями — роли назначаются
  через CLI `app.cli` (Sprint 8).
- Нет подтверждения email, восстановления пароля и rate limiting.
- Нет загрузки обложек и содержимого уроков: `cover_image_url` — только ссылка,
  `content` — только Markdown-текст (файлы/видео появятся позже).
- Публичная карточка курса показывает структуру (названия модулей и уроков), но
  не содержимое уроков; материалы открываются после записи через
  `/api/v1/learning/...`. Автор проверяет черновики через авторский API курсов.
- Прогресс не материализуется в отдельной таблице: он пересчитывается при
  чтении и после изменений структуры под блокировкой строки записи.
- Сортировка каталога по названию использует колляцию PostgreSQL по умолчанию;
  локализованная сортировка не реализована.
- `python` из Windows Store является заглушкой — используйте `py` или
  `backend\.venv\Scripts\python.exe`.
- Vite привязан к `127.0.0.1:5173` (не к `localhost`): подключение к `[::1]:5173`
  на этой машине блокируется.
