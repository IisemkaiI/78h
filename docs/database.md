# База данных

## 1. Состояние после Sprint 6

PostgreSQL 17 работает в Docker Compose. Схема создаётся и версионируется
Alembic-миграциями; `create_all()` в приложении не используется. Текущая
ревизия — `0008_certificates`.

Проверка ревизии `0008_certificates` выполнена на PostgreSQL: upgrade,
downgrade до `0007_assessment_lesson_retention`, повторный upgrade и
`alembic check` без drift.

Таблицы:

| Таблица | Назначение |
| --- | --- |
| `users` | зарегистрированные аккаунты |
| `roles` | системные роли (`guest`, `user`, `course_author`, ...) |
| `permissions` | атомарные разрешения (`profile:read`, `courses:create`, ...) |
| `user_roles` | связь многие-ко-многим пользователь ↔ роль |
| `role_permissions` | связь многие-ко-многим роль ↔ разрешение |
| `categories` | категории курсов (8 засеянных) |
| `courses` | курсы: метаданные, статус, автор, категория |
| `course_modules` | модули курса с позицией |
| `lessons` | уроки модуля с позицией и Markdown-текстом |
| `enrollments` | запись пользователя на курс (одна на пару) |
| `lesson_progress` | состояние урока и снимки удалённых уроков |
| `learning_events` | журнал обучения: записи, старт, завершение |
| `course_instructors` | назначения преподавателей на курсы |
| `certificates` | неизменяемые снимки выданных сертификатов, по одному на enrollment |
| `quizzes`, `quiz_questions` | тесты и версии вопросов/критериев |
| `quiz_attempts`, `quiz_answers` | попытки со снимками теста и ответами |
| `practical_assignments` | практические задания курса |
| `assignment_submissions` | состояние работы обучающегося |
| `submission_versions` | неизменяемые версии отправленного ответа |
| `assignment_reviews` | решения преподавателей, оценки и комментарии |
| `alembic_version` | текущая ревизия схемы |

Таблиц сертификации и организаций пока нет.

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

Ревизия `0002_seed_rbac` создаёт базовые данные идемпотентно
(`ON CONFLICT DO NOTHING`), не удаляя ничего существующего.

Таблица показывает текущие назначения после применения `0006_assessments`:

| Роль | Кол-во разрешений |
| --- | --- |
| `guest` | 0 |
| `user` | 13 |
| `course_author` | 19 |
| `teacher` | 14 |
| `organization_employee` | 13 |
| `organization_manager` | 16 |
| `admin` | 32 |

Всего 32 уникальных разрешения. Sprint 2 добавил `courses:delete` и
`courses:manage_all`, а `course_author` получил `courses:create`,
`courses:update`, `courses:publish` и `courses:delete`. Sprint 4 добавил
`enrollments:create`, `enrollments:read_own`, `enrollments:cancel_own`,
`enrollments:manage_all`, `progress:read_own`, `progress:update_own` и
`progress:manage_all`; первые пять из них получили все роли, кроме `guest`
(полный набор `*:manage_all` — только `admin`).

Sprint 5 добавил восемь разрешений `assessments:*`: пользователи получили
`attempt`, `read_own_results` и `submit`; авторы дополнительно получили
`manage_own`, `publish_own` и `instructors_manage`; преподаватели — `review`;
администратор получил полный набор.

Разрешения сгруппированы по модулям: `profile:*`, `courses:*`,
`learning:*`, `enrollments:*`, `progress:*`, `teaching:*`, `organization:*`,
`admin:*`. Матрица ролей зафиксирована в миграциях, чтобы исторические
ревизии оставались воспроизводимыми. Легаси-разрешения `learning:enroll` и
`learning:participate` не удаляются и не используются новыми проверками.

`guest` — не аккаунт, а обозначение неавторизованного посетителя. Роль
существует для полноты модели, не имеет разрешений и никогда не назначается
записи в `users`.

## 5. Курсы и категории

### `categories`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK |
| `name` | `varchar(120)` | NOT NULL |
| `slug` | `varchar(120)` | NOT NULL, UNIQUE (`uq_categories_slug`), индекс `ix_categories_slug` |
| `description` | `varchar(1000)` | NULL |
| `is_active` | `boolean` | NOT NULL, default `true` |
| `created_at`, `updated_at` | `timestamptz` | NOT NULL, default `now()` |

Только активные категории видны в публичном API. 8 категорий засеяны
идемпотентно ревизией `0004_seed_courses`.

### `courses`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK |
| `title` | `varchar(200)` | NOT NULL |
| `slug` | `varchar(220)` | NOT NULL, UNIQUE (`uq_courses_slug`), индекс `ix_courses_slug` |
| `short_description` | `varchar(300)` | NOT NULL |
| `description` | `text` | NOT NULL |
| `cover_image_url` | `varchar(500)` | NULL |
| `level` | `varchar(20)` | NOT NULL, CHECK `ck_courses_level_values` (`beginner`, `intermediate`, `advanced`) |
| `language` | `varchar(10)` | NOT NULL |
| `status` | `varchar(20)` | NOT NULL, default `draft`, CHECK `ck_courses_status_values` (`draft`, `published`, `archived`) |
| `author_id` | `uuid` | FK → `users.id` ON DELETE CASCADE, индекс `ix_courses_author_id` |
| `category_id` | `uuid` | FK → `categories.id`, индекс `ix_courses_category_id` |
| `published_at` | `timestamptz` | NULL |
| `created_at`, `updated_at` | `timestamptz` | NOT NULL, default `now()` |

Slug генерируется из заголовка (включая транслитерацию кириллицы) с
числовым суффиксом при коллизии и никогда не изменяется. `published_at`
устанавливается при первом переходе в `published` и сохраняется при
повторных публикациях.

### `course_modules` и `lessons`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `course_modules.id` | `uuid` | PK |
| `course_modules.course_id` | `uuid` | FK → `courses.id` ON DELETE CASCADE, индекс |
| `course_modules.title` | `varchar(200)` | NOT NULL |
| `course_modules.description` | `varchar(2000)` | NULL |
| `course_modules.position` | `integer` | NOT NULL |
| `lessons.id` | `uuid` | PK |
| `lessons.module_id` | `uuid` | FK → `course_modules.id` ON DELETE CASCADE, индекс |
| `lessons.title` | `varchar(200)` | NOT NULL |
| `lessons.description` | `varchar(2000)` | NULL |
| `lessons.content` | `text` | NOT NULL (Markdown) |
| `lessons.position` | `integer` | NOT NULL |
| `lessons.estimated_duration_minutes` | `integer` | NOT NULL, default 0, CHECK `ck_lessons_estimated_duration_minutes_non_negative` |

Уникального ограничения на `position` нет: перестановка выполняется
транзакционно (временно отрицательные позиции, затем 1..n), а удаление
элемента перенумеровывает остальные в той же транзакции. Каскадное удаление
на уровне БД (`ON DELETE CASCADE` + `passive_deletes=True` в ORM) гарантирует,
что не останется «сирот».

## 6. Обучение

Ревизия `0005_learning` создаёт три таблицы и семь разрешений. Материализованной
таблицы прогресса нет: `CourseProgress` вычисляется из текущей структуры курса и
`lesson_progress`, а `enrollments.completed_at` служит производной отметкой.

### `enrollments`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id` ON DELETE CASCADE, индекс |
| `course_id` | `uuid` | FK → `courses.id` ON DELETE RESTRICT, индекс |
| `status` | `varchar(20)` | NOT NULL, default `active`, CHECK `ck_enrollments_status_values` (`active`, `cancelled`) |
| `enrolled_at` | `timestamptz` | NOT NULL, default `now()` |
| `started_at`, `completed_at`, `cancelled_at`, `last_activity_at` | `timestamptz` | NULL |
| `created_at`, `updated_at` | `timestamptz` | NOT NULL, default `now()` |

UNIQUE (`user_id`, `course_id`) — одна строка на пару; отмена и повторная
запись переиспользуют её. `completed_at` синхронизируется с фактическим
прогрессом. `ON DELETE RESTRICT` защищает историю от физического удаления
курса; сервис дополнительно отвечает `409 course_has_enrollments`.

### `lesson_progress`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK |
| `enrollment_id` | `uuid` | FK → `enrollments.id` ON DELETE CASCADE |
| `lesson_id` | `uuid` | FK → `lessons.id` ON DELETE SET NULL, NULL после удаления урока |
| `lesson_id_original` | `uuid` | NOT NULL, неизменяемый идентификатор урока |
| `module_id_original` | `uuid` | NOT NULL |
| `lesson_title_snapshot`, `module_title_snapshot` | `varchar(200)` | NOT NULL, снимок на момент действия |
| `state` | `varchar(20)` | NOT NULL, default `not_started`, CHECK `ck_lesson_progress_state_values` |
| `started_at`, `completed_at`, `last_viewed_at` | `timestamptz` | NULL |
| `created_at`, `updated_at` | `timestamptz` | NOT NULL, default `now()` |

UNIQUE (`enrollment_id`, `lesson_id_original`) и индекс
(`enrollment_id`, `state`). Снимки названий позволяют показать удалённый урок в
истории.

### `learning_events`

| Колонка | Тип | Ограничения |
| --- | --- | --- |
| `id` | `uuid` | PK |
| `enrollment_id` | `uuid` | FK → `enrollments.id` ON DELETE CASCADE |
| `lesson_id` | `uuid` | FK → `lessons.id` ON DELETE SET NULL |
| `lesson_id_original` | `uuid` | NULL |
| `event_type` | `varchar(30)` | NOT NULL, CHECK `ck_learning_events_event_type_values` |
| `payload` | `jsonb` | NOT NULL, default `{}` |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |

Типы событий: `enrolled`, `cancelled`, `reactivated`, `started`,
`lesson_started`, `lesson_completed`, `lesson_reopened`, `lesson_reset`,
`course_completed`, `course_reopened`. Индексы: (`enrollment_id`,
`created_at`) и `lesson_id`.

## 7. Тесты и практические задания

Миграция `0006_assessments` создаёт девять таблиц и разрешения Sprint 5;
`0007_assessment_lesson_retention` делает `lesson_id` nullable с `ON DELETE SET NULL`, чтобы удаление урока не удаляло историю проверки.

### Основные сущности

- `course_instructors`: уникальная пара `course_id`/`instructor_id`, автор
  назначения и время создания. Назначение можно снять, не затрагивая отзывы.
- `quizzes`: статус, обязательность, проходной процент, лимит времени/попыток
  и версия содержимого. `quiz_questions` хранит тип, формулировку, варианты,
  ключ ответа, баллы и позицию.
- `quiz_attempts`: пользователь, запись, версия теста и JSONB-снимок вопросов;
  результат, процент, `passed`, время старта/завершения и статус.
- `quiz_answers`: ответы и начисленные баллы по ключу вопроса.
- `practical_assignments`: описание, требования, максимальные баллы,
  обязательность, возможность повторной отправки и статус публикации.
- `assignment_submissions`: одна работа на пару assignment/user, текущий статус,
  последняя версия, текущая оценка и флаг принятия.
- `submission_versions`: неизменяемый текст и номер каждой отправки.
- `assignment_reviews`: решение, оценка, комментарий, версия работы и reviewer.

Попытки хранят снимок критериев на старте; авторские правки не меняют
историческую проверку. Удаление теста/задания блокируется при существующей
истории ограничениями FK; архивирование сохраняет данные.

### Прогресс

`CourseProgress` включает `total_required_assessments` и
`completed_required_assessments`. В знаменатель попадают текущие уроки и
опубликованные обязательные проверки. Тест становится завершённым после
проходной попытки; практическая работа — только после решения `accepted`.
Неуспешные тесты, черновики, `submitted`, `under_review` и
`revision_required` не завершают проверку. Архивированные проверки исключаются
из текущего прогресса без удаления истории. Пересчёт и синхронизация
`enrollments.completed_at` происходят в транзакции с событием изменения.

Согласованность прогресса и структуры описана в `docs/api.md`, раздел
«Обучение»: пересчёт выполняется после каждого изменения прогресса и структуры
курса в той же транзакции; чтение прогресса дополнительно чинит устаревшую
отметку под `SELECT ... FOR UPDATE`.

## 8. Миграции

Файлы:

```
backend/alembic.ini
backend/alembic/env.py                 async-движок, DSN из Settings
backend/alembic/versions/0001_users_rbac.py
backend/alembic/versions/0002_seed_rbac.py
backend/alembic/versions/0003_courses.py
backend/alembic/versions/0004_seed_courses.py
backend/alembic/versions/0005_learning.py
backend/alembic/versions/0006_assessments.py
backend/alembic/versions/0007_assessment_lesson_retention.py
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

## 9. Docker Compose

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

## 10. Подключение из приложения

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

## 11. Проверка готовности

`ping_database()` выполняет `SELECT 1` с ограничением `DB_READY_TIMEOUT` (3 с):

- успех → `/api/v1/ready` отвечает `200`, `"status": "ready"`,
  `database.status = "available"`, `latency_ms` — измеренная задержка;
- ошибка/таймаут → `503`, `"status": "not_ready"`,
  `database.status = "unavailable"`, `detail` — короткая категория проблемы
  (например, `ConnectionRefusedError`) без хостов, логинов и паролей.

## 12. Тестовая база

Integration-тесты используют отдельную базу `education_platform_test`
(переопределяется `TEST_POSTGRES_DB`). `tests/integration/conftest.py`:

1. создаёт базу, если её нет (через asyncpg и служебную БД `postgres`);
2. применяет `alembic upgrade head` с `ALEMBIC_DATABASE_URL`;
3. создаёт async-движок с `NullPool`;
4. очищает `learning_events`, `lesson_progress`, `enrollments`, `lessons`,
   `course_modules`, `courses`, `user_roles` и `users` перед каждым тестом
   (`TRUNCATE ... CASCADE`), сохраняя засеянные роли, разрешения и категории.

SQLite не используется: тесты проверяют настоящее поведение PostgreSQL.

## 13. Проверка вручную

```powershell
cd D:\education-platform
docker compose up -d postgres
docker compose ps                     # healthy

cd backend
.\.venv\Scripts\alembic.exe upgrade head

docker exec education-platform-postgres psql -U edu_platform -d education_platform -c "\dt"
docker exec education-platform-postgres psql -U edu_platform -d education_platform `
  -c "select r.code, count(rp.permission_id) from roles r left join role_permissions rp on rp.role_id=r.id group by r.code order by r.code;"

docker exec education-platform-postgres psql -U edu_platform -d education_platform `
  -c "select status, count(*) from enrollments group by status;"

docker exec education-platform-postgres psql -U edu_platform -d education_platform `
  -c "select event_type, count(*) from learning_events group by event_type order by event_type;"

docker exec education-platform-postgres psql -U edu_platform -d education_platform `
  -c "select lesson_id, lesson_id_original, state from lesson_progress where lesson_id is null;"
```

Сохранение данных после перезапуска backend:

1. зарегистрировать пользователя через API;
2. остановить и снова запустить uvicorn;
3. выполнить `POST /api/v1/auth/login` с теми же данными — вход должен пройти;
4. проверить запись в `users` через `psql`.

Сохранение после перезапуска контейнера проверяется `docker compose restart postgres`.

## 14. Диагностика

| Симптом | Причина | Решение |
| --- | --- | --- |
| `/ready` → `503`, `detail: "ConnectionRefusedError"` | контейнер не запущен | `docker compose up -d postgres` |
| `/ready` → `503`, `detail: "TimeoutError"` | контейнер стартует | дождаться `healthy` |
| `password authentication failed` | `.env` изменён после создания контейнера | пересоздать том (удалит данные) или вернуть пароль |
| `relation "users" does not exist` | миграции не применены | `alembic upgrade head` |
| `Role 'user' is missing from the database` (500) | seed-миграция не применена | `alembic upgrade head` |
| `duplicate key value violates unique constraint "uq_courses_slug"` | одинаковые заголовки у курсов одного автора | slug получает числовой суффикс автоматически |
| `new row violates check constraint "ck_courses_status_values"` | клиент передал неверный статус | статус выставляет сервер, используйте `/publish` |
| `new row violates check constraint "ck_lesson_progress_state_values"` | недопустимое состояние урока | используйте `not_started`, `in_progress` или `completed` |
| `duplicate key ... uq_enrollments_user_id_course_id` | конкурентная первая запись | повторите запрос: активная запись уже создана |
| `update or delete on table "courses" violates foreign key ... enrollments` | физическое удаление курса с записями | архивируйте курс; API отвечает `409 course_has_enrollments` |
| `JWT_SECRET must be set...` при старте | нет секрета в `.env` | сгенерировать и добавить `JWT_SECRET` |
| порт 5432 занят | локальный PostgreSQL | изменить `POSTGRES_PORT` |
| тесты идут в рабочую базу | не задан `TEST_POSTGRES_DB`/конфиг conftest | проверить `tests/integration/conftest.py` |
