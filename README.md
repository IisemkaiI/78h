# Education Platform

Технический фундамент многофункциональной образовательной LMS-платформы.
Репозиторий содержит только инфраструктурную основу (**Sprint 0**): React-клиент,
FastAPI-бэкенд, подготовленное подключение к PostgreSQL и документацию.
Функциональные модули (пользователи, каталог курсов, обучение, тестирование,
сертификация, корпоративный кабинет, админ-панель) появятся в следующих спринтах.

## Статус Sprint 0

| Критерий | Статус |
| --- | --- |
| Структура проекта | готово |
| Frontend запускается (Vite) | проверено |
| Production-сборка и TypeScript | проверено |
| Backend запускается (uvicorn) | проверено |
| Frontend → Backend (health/info/ready) | проверено в браузере |
| Docker Compose для PostgreSQL | файл подготовлен, **не проверен запуском** |
| Подключение Backend → PostgreSQL | код готов, **не проверено** (Docker отсутствует) |
| Git-репозиторий и первый коммит | готово |
| Документация | готово |

Подробный отчёт о проверках — в конце сессии Sprint 0 и в
[`docs/development-plan.md`](docs/development-plan.md).

## Технологии

**Frontend:** React 19, TypeScript 5.9, Vite 7.
**Backend:** Python 3.14, FastAPI, Uvicorn, SQLAlchemy 2 (async), asyncpg, Pydantic 2, pydantic-settings.
**База данных:** PostgreSQL 17 (официальный образ `postgres:17-alpine`).
**Инфраструктура:** Docker Compose, Git.
**Тесты:** pytest, pytest-asyncio, httpx.

Redis, Celery и APScheduler в Sprint 0 не подключаются.

## Структура каталогов

```
education-platform/
├── frontend/                     React + TypeScript + Vite
│   ├── public/                   статические файлы
│   ├── src/
│   │   ├── app/                  корневой компонент и его стили
│   │   ├── assets/               изображения/иконки
│   │   ├── components/           переиспользуемые компоненты (ConnectionStatus)
│   │   ├── hooks/                useBackendStatus
│   │   ├── modules/              место для будущих доменных модулей (пока пусто)
│   │   ├── services/             apiClient, systemService
│   │   ├── styles/               variables.css (дизайн-токены), global.css
│   │   ├── types/                контракты API
│   │   ├── main.tsx
│   │   └── vite-env.d.ts
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── backend/                      FastAPI
│   ├── app/
│   │   ├── api/v1/               версионируемый API (endpoints, schemas, router)
│   │   ├── core/                 config.py, database.py, errors.py
│   │   ├── modules/              будущие доменные модули (пока пусто)
│   │   ├── workers/              будущие фоновые задачи (пока пусто)
│   │   └── main.py
│   ├── tests/                    pytest: unit + integration (маркер integration)
│   ├── pytest.ini
│   ├── requirements.txt
│   └── requirements-dev.txt
├── infrastructure/
│   ├── docker/                   пояснения к контейнерам (+ место под init-скрипты)
│   └── scripts/                  check-environment.ps1
├── docs/
│   ├── architecture.md
│   ├── database.md
│   ├── api.md
│   └── development-plan.md
├── docker-compose.yml            PostgreSQL
├── .env.example                  шаблон секретов (копируется в .env)
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
| Docker Desktop | **не установлен — требуется установка** |

Автоматическая проверка окружения:

```powershell
powershell -ExecutionPolicy Bypass -File infrastructure/scripts/check-environment.ps1
```

Скрипт ничего не устанавливает и не меняет. Он показывает наличие инструментов,
состояние WSL и Docker; код возврата `1` означает, что часть проверок невозможна.

## Переменные окружения

### Корневой `.env`

Используется и Docker Compose, и бэкендом — единственный источник параметров БД.

```powershell
Copy-Item .env.example .env
# затем задайте свой POSTGRES_PASSWORD
```

| Переменная | Назначение | Пример |
| --- | --- | --- |
| `PROJECT_NAME` | Название приложения | `Education Platform` |
| `PROJECT_VERSION` | Версия проекта | `0.1.0` |
| `APP_ENV` | Окружение: `local`/`test`/`staging`/`production` | `local` |
| `DEBUG` | SQL echo и подробные логи | `false` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `API_V1_PREFIX` | Префикс версионированного API | `/api/v1` |
| `BACKEND_HOST`, `BACKEND_PORT` | Адрес, на котором публикуется backend | `127.0.0.1`, `8000` |
| `CORS_ORIGINS` | Разрешённые origin'ы фронтенда (через запятую) | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173` |
| `POSTGRES_HOST` | Хост БД с точки зрения backend | `127.0.0.1` |
| `POSTGRES_PORT` | Порт, публикуемый контейнером | `5432` |
| `POSTGRES_USER` | Пользователь БД | `edu_platform` |
| `POSTGRES_PASSWORD` | Пароль БД (секрет) | — |
| `POSTGRES_DB` | Имя базы проекта | `education_platform` |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT` | Пул соединений | `5`, `10`, `30` |
| `DB_CONNECT_TIMEOUT` | Таймаут установки соединения, с | `5` |
| `DB_READY_TIMEOUT` | Таймаут проверки готовности, с | `3` |

### `frontend/.env`

```powershell
Copy-Item frontend/.env.example frontend/.env
```

| Переменная | Назначение | Пример |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Базовый URL backend для браузера | `http://127.0.0.1:8000` |

Файлы `.env` находятся в `.gitignore`. В репозиторий попадают только `.env.example`.

## Запуск PostgreSQL через Docker

> Docker Desktop на текущей машине **не установлен**, поэтому этот шаг пока
> не выполнялся. Инструкция по установке — ниже.

```powershell
cd D:\education-platform
docker compose up -d postgres
docker compose ps                  # STATUS должен стать healthy
docker compose logs -f postgres
```

Остановка без потери данных:

```powershell
docker compose down
```

Полное удаление данных (том `education-platform-postgres-data`):

```powershell
docker compose down -v
```

## Запуск Backend

```powershell
cd D:\education-platform\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Если PowerShell блокирует активацию виртуального окружения:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Без активации окружения:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe http://127.0.0.1:8000/api/v1/ready
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

> Если PowerShell выдаёт `npm.ps1 cannot be loaded because running scripts is
> disabled`, используйте `npm.cmd` вместо `npm` либо один раз выполните
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Адреса служебных API

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/v1/health` | Процесс жив, БД не затрагивается |
| GET | `/api/v1/ready` | Готовность: реальная проверка `SELECT 1` в PostgreSQL |
| GET | `/api/v1/info` | Название приложения и версия проекта |
| GET | `/docs` | Swagger UI (OpenAPI) |

`/api/v1/ready` возвращает `503` и `"status": "not_ready"`, если база недоступна.
Подробности — в [`docs/api.md`](docs/api.md).

## Тесты

```powershell
cd D:\education-platform\backend
.\.venv\Scripts\python.exe -m pytest            # unit-тесты, БД не требуется
.\.venv\Scripts\python.exe -m pytest -m integration   # требует запущенного PostgreSQL
```

Integration-тесты исключены из обычного запуска настройкой `pytest.ini`, чтобы
локальная разработка не зависела от Docker. Они не считаются пройденными, пока
контейнер PostgreSQL не запущен.

## Установка Docker Desktop и WSL2

Выполняется пользователем вручную (агент не изменяет системные настройки).

1. **Проверьте виртуализацию.** Диспетчер задач → «Производительность» → «ЦП» →
   строка «Виртуализация» должна быть «Включена». Если выключена — включите
   `Intel VT-x` / `AMD-V` в BIOS/UEFI.
2. **Установите WSL2** (PowerShell от имени администратора):
   ```powershell
   wsl --install
   wsl --set-default-version 2
   ```
   После установки перезагрузите компьютер и создайте пользователя Linux
   (логин/пароль для Ubuntu).
3. **Проверьте WSL:**
   ```powershell
   wsl --status
   wsl --list --verbose
   ```
   В списке должен быть дистрибутив (например, `Ubuntu`) с версией `2`.
4. **Установите Docker Desktop:**
   ```powershell
   winget install --id Docker.DockerDesktop --exact
   ```
   Либо скачайте установщик: <https://www.docker.com/products/docker-desktop/>.
5. **Запустите Docker Desktop**, дождитесь статуса «Engine running».
   В настройках: *Settings → General → Use the WSL 2 based engine* — включено;
   *Settings → Resources → WSL Integration* — включён ваш дистрибутив.
6. **Проверьте установку:**
   ```powershell
   docker --version
   docker compose version
   docker run --rm hello-world
   ```
7. **Запустите базу и проверьте готовность:**
   ```powershell
   cd D:\education-platform
   docker compose up -d postgres
   docker compose ps
   curl.exe http://127.0.0.1:8000/api/v1/ready
   ```
   Ожидаемый ответ `/ready`: `"status":"ready"`, `"database":{"status":"available",...}`.

Если Docker Desktop не запускается и предлагает включить компоненты Windows,
разрешите установку WSL2 и «Virtual Machine Platform», затем перезагрузитесь.

## Git

Первый коммит:

```
chore: initialize education platform foundation
```

`.gitignore` исключает `node_modules`, виртуальные окружения Python,
`__pycache__`, `.env`, логи, кеши, сборки и локальные временные файлы.

## Известные ограничения Sprint 0

- Docker отсутствует: `docker-compose.yml` и подключение к PostgreSQL **не проверены запуском**.
- `python` из Windows Store является заглушкой — используйте `py` или `backend\.venv\Scripts\python.exe`.
- Vite привязан к `127.0.0.1:5173` (не к `localhost`): на этой машине подключение
  к `[::1]:5173` блокируется, поэтому IPv4 задан явно.
- Миграции (Alembic), аутентификация, доменные таблицы и фоновые задачи появятся
  в следующих спринтах.
