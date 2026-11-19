# Education Platform

Многофункциональная образовательная LMS-платформа. Репозиторий содержит
фундамент проекта (**Sprint 0**) и базовую систему пользователей (**Sprint 1**):
React-клиент, FastAPI-бэкенд, PostgreSQL, Alembic-миграции, регистрацию, вход по
JWT, личный профиль и реляционную ролевую модель (RBAC).

Модули каталога курсов, обучения, тестирования, сертификации, корпоративного
кабинета и админ-панели появятся в следующих спринтах.

## Статус Sprint 1

| Критерий | Статус |
| --- | --- |
| PostgreSQL 17 в Docker Compose | проверено (healthy) |
| Alembic-миграции схемы | применены, `alembic upgrade head` |
| Системные роли и разрешения | засеяны миграцией (7 ролей, 15 разрешений) |
| Регистрация с базовой ролью `user` | проверено |
| Вход по email/паролю, JWT access token | проверено |
| Личный профиль (`GET/PATCH /users/me`) | проверено |
| RBAC-зависимости ролей и разрешений | проверено тестами |
| Защита от самостоятельного назначения ролей | проверено тестами |
| Frontend: `/login`, `/register`, `/profile` | проверено в браузере |
| Сохранение сессии после перезагрузки | проверено |
| Backend-тесты (unit + PostgreSQL) | 6 unit + 55 integration, все зелёные |
| Production-сборка frontend и TypeScript | проверено |
| Документация | обновлена |

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

Redis, Celery и APScheduler в Sprint 1 не подключаются.

## Структура каталогов

```
education-platform/
├── frontend/                     React + TypeScript + Vite
│   ├── public/                   статические файлы
│   ├── src/
│   │   ├── app/                  App, AppLayout, стили оболочки
│   │   ├── assets/               изображения/иконки
│   │   ├── auth/                 AuthProvider, ProtectedRoute
│   │   ├── components/           ConnectionStatus
│   │   ├── hooks/                useBackendStatus
│   │   ├── modules/              место для будущих доменных модулей
│   │   ├── pages/                HomePage, LoginPage, RegisterPage, ProfilePage
│   │   ├── services/             apiClient, authService, tokenStorage, systemService
│   │   ├── styles/               дизайн-токены, global.css, ui.css
│   │   ├── types/                контракты API
│   │   ├── utils/                валидация форм, сообщения об ошибках, подписи ролей
│   │   ├── main.tsx
│   │   └── vite-env.d.ts
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── backend/                      FastAPI
│   ├── alembic/                  env.py и ревизии 0001 (схема), 0002 (seed RBAC)
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py           SessionDep
│   │   │   └── v1/               router, endpoints (system, auth, users)
│   │   ├── core/                 config, database, errors, security
│   │   ├── modules/
│   │   │   ├── auth/             AuthService, get_current_user, require_roles/permissions
│   │   │   └── users/            модели, RBAC-коды, репозиторий, сервис, схемы
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
| `PROJECT_VERSION` | Версия проекта | `0.2.0` |
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
миграциями. Ревизия `0002_seed_rbac` идемпотентно создаёт системные роли и
разрешения (`ON CONFLICT DO NOTHING`) и не удаляет существующие данные.

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

Полное описание схем, кодов ошибок и примеров — в [`docs/api.md`](docs/api.md).

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
тестами таблицы пользователей очищаются. SQLite не используется.

Фактический прогон Sprint 1 (2026-11-19):

```
pytest                     -> 6 passed
pytest -m integration      -> 55 passed
npm run typecheck          -> ok
npm run build              -> ok
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

История Sprint 0 не переписывалась. Sprint 1 оформлен логическими коммитами
(backend, frontend, docs). `.gitignore` исключает `node_modules`, виртуальные
окружения Python, `__pycache__`, `.env`, логи, кеши, сборки и временные файлы.

## Известные ограничения Sprint 1

- JWT нельзя отозвать до истечения срока (нет denylist/refresh-токенов).
- Нет административного API и панели управления ролями — роли назначаются
  внутренними средствами/миграциями.
- Нет подтверждения email и восстановления пароля.
- Нет rate limiting и блокировки после неудачных попыток входа.
- `python` из Windows Store является заглушкой — используйте `py` или
  `backend\.venv\Scripts\python.exe`.
- Vite привязан к `127.0.0.1:5173` (не к `localhost`): подключение к `[::1]:5173`
  на этой машине блокируется.
