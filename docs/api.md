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
- [Обучение](#обучение)
- [Тесты и практические задания](#тесты-и-практические-задания)
- [Сертификаты](#сертификаты)
- [Корпоративное обучение](#корпоративное-обучение-sprint-8-этап-4)
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
  "version": "0.6.0",
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
  "version": "0.6.0",
  "database": { "status": "available", "detail": null, "latency_ms": 1.84 }
}
```

**503 — база недоступна**

```json
{
  "status": "not_ready",
  "version": "0.6.0",
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
  "version": "0.6.0",
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
гость видит только описание и программу. Материалы уроков доступны через
защищённый API обучения после записи на курс (см. раздел «Обучение»).

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
Ответ `204`. Если у курса есть хотя бы одна запись обучающегося (включая
отменённую), удаление блокируется: `409 course_has_enrollments` — используйте
архивацию, чтобы сохранить историю обучения.

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

## Обучение

Префикс: `/api/v1/learning`. Все эндпоинты требуют Bearer-токен. Обычный
обучающийся работает только со своими записями; администратор с
`enrollments:manage_all` / `progress:manage_all` получает доступ ко всем
записям. Чужая запись, как и несуществующая, возвращает `404
enrollment_not_found`.

### Запись на курс

| Метод | Путь | Назначение | Разрешение |
| --- | --- | --- | --- |
| POST | `/enrollments` | Записаться или возобновить отменённую запись | `enrollments:create` |
| GET | `/enrollments/mine` | Свои записи с прогрессом | `enrollments:read_own` |
| GET | `/enrollments/by-course/{course_id}` | Статус записи по курсу | `enrollments:read_own` |
| GET | `/enrollments` | Все записи (администратор) | `enrollments:manage_all` |
| GET | `/enrollments/{id}` | Одна запись | `enrollments:read_own` |
| DELETE | `/enrollments/{id}` | Отменить запись | `enrollments:cancel_own` |
| POST | `/enrollments/{id}/start` | Идемпотентно отметить старт курса | `progress:update_own` |

`POST /enrollments` принимает `{ "course_id": "uuid" }`. Новый ряд — `201`,
возобновление ранее отменённого — `200`; в обоих случаях возвращается
`EnrollmentRead`. Одна пара «пользователь + курс» имеет ровно одну строку,
поэтому повторная запись не создаёт дубликат и не теряет прогресс.
Отмена переводит строку в `cancelled`, сохраняя уроки, историю и
`completed_at`.

Правила записи:

- курс должен быть `published`, а его категория — активной, иначе
  `404 course_not_found`;
- автор не может записаться на собственный курс —
  `403 own_course_enrollment_forbidden`;
- повторная запись при активной записи — `409 already_enrolled`
  (в том числе при конкурентных запросах).

### Прогресс и журнал

| Метод | Путь | Назначение | Разрешение |
| --- | --- | --- | --- |
| GET | `/enrollments/{id}/progress` | Текущий прогресс курса | `progress:read_own` |
| GET | `/enrollments/{id}/history` | Журнал событий и удалённые уроки | `progress:read_own` |
| PUT | `/enrollments/{id}/lessons/{lesson_id}/progress` | Установить состояние урока | `progress:update_own` |

Состояния урока: `not_started`, `in_progress`, `completed`. Тело запроса —
`{ "state": "completed" }`. Ответ содержит обновлённый урок и актуальный
`course_progress`.

`progress_percent` вычисляется на сервере как
`floor(completed_lessons * 100 / total_lessons)`; для курса без уроков — `0`.
`is_completed` истинно только когда все **текущие** уроки завершены; пустой
курс завершённым не считается.

Согласованность:

- `enrollments.completed_at` — производная отметка, а не источник истины;
- после каждого изменения прогресса и после изменения структуры курса
  (добавление/удаление урока или модуля) все записи курса пересчитываются в
  той же транзакции;
- чтение прогресса также чинит устаревшую отметку под блокировкой строки;
- события `course_completed` и `course_reopened` пишутся только при реальном
  переходе;
- новый урок уменьшает процент и снимает устаревшую отметку завершения;
- удаление урока сохраняет снимок (`lesson_id_original`, названия урока и
  модуля) в `lesson_progress` и `learning_events`; `lesson_id` становится
  `NULL` по `ON DELETE SET NULL`.

`removed_lessons_count` — количество уникальных удалённых уроков, по которым
есть строка прогресса или событие журнала. Урок, добавленный и удалённый без
действий обучающегося, счётчик не увеличивает.

### Материалы курса

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/courses/{slug}` | Программа с состояниями уроков, без `content` |
| GET | `/courses/{slug}/lessons/{lesson_id}` | Полный Markdown-контент урока |

Оба эндпоинта требуют активную запись на опубликованный курс. Если записи
нет — `403 enrollment_required`; если курс снят с публикации или его категория
отключена — `409 course_not_available` (запись при этом сохраняется). Ответы
помечены `Cache-Control: private, no-store`.

Администратор с `enrollments:manage_all` может читать опубликованный курс без
собственной записи. Автор проверяет свои уроки, включая черновики, через
авторский `GET /api/v1/courses/{id}`; публичный API обучения черновики не
раскрывает.

### Ошибки обучения

| Код | HTTP | Когда |
| --- | --- | --- |
| `enrollment_required` | 403 | нет активной записи |
| `own_course_enrollment_forbidden` | 403 | автор пытается записаться на свой курс |
| `already_enrolled` | 409 | активная запись уже существует |
| `enrollment_cancelled` | 409 | отмена уже отменённой записи |
| `course_not_found` | 404 | курс не опубликован/не существует |
| `course_not_available` | 409 | курс или категория закрыты для обучения |
| `enrollment_not_found` | 404 | запись не существует или чужая |
| `lesson_not_found` | 404 | урок не принадлежит курсу |
| `course_has_enrollments` | 409 | попытка удалить курс с записями |

## Тесты и практические задания

Префикс: `/api/v1/assessments`. Защищённые методы требуют Bearer-токен.
Автор управляет проверками своего курса; преподаватель работает только с
курсами, на которые назначен; администратор действует с административными
разрешениями. Обучающийся может проходить проверки только при активной записи
на опубликованный курс.

### Авторские проверки

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | `/quizzes` | Создать черновик теста с вопросами |
| GET | `/courses/{course_id}/quizzes` | Список тестов курса |
| GET | `/quizzes/{quiz_id}` | Прочитать тест для редактирования |
| PATCH | `/quizzes/{quiz_id}` | Обновить тест; опубликованная правка создаёт следующую версию |
| POST | `/quizzes/{quiz_id}/publish` | Опубликовать тест |
| POST | `/quizzes/{quiz_id}/unpublish` | Снять публикацию |
| POST | `/quizzes/{quiz_id}/archive` | Архивировать, сохраняя историю |
| POST | `/assignments` | Создать черновик практического задания |
| PATCH | `/assignments/{assignment_id}` | Обновить задание |
| POST | `/assignments/{assignment_id}/publish` | Опубликовать задание |
| POST | `/assignments/{assignment_id}/unpublish` | Снять публикацию |
| POST | `/assignments/{assignment_id}/archive` | Архивировать задание |

Вопросы поддерживают `single_choice`, `multiple_choice`, `true_false` и
`short_text`. У вопроса задаются формулировка, варианты для выбора, ключ
проверки, баллы и позиция. Тест задаёт `passing_score_percent`,
`time_limit_minutes`, `max_attempts` и `is_required`. Попытка сохраняет номер
версии и снимок вопросов, вариантов и ключей на момент старта; последующее
редактирование теста не изменяет старые результаты. Ключи ответов не выдаются
до отправки попытки.

Обязательность опубликованного материала нельзя менять обычным обновлением;
материал нужно снять с публикации, изменить и опубликовать снова. Архивирование
не удаляет попытки, отправки и отзывы.

### Прохождение тестов и практики

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | `/quizzes/{quiz_id}/attempts` | Начать попытку (создать снимок) |
| PUT | `/attempts/{attempt_id}/answers` | Сохранить ответы |
| POST | `/attempts/{attempt_id}/submit` | Завершить и проверить попытку |
| GET | `/quizzes/{quiz_id}/attempts/mine` | История собственных попыток |
| PUT | `/assignments/{assignment_id}/submission/draft` | Сохранить черновик практики |
| POST | `/assignments/{assignment_id}/submission/submit` | Отправить новую версию работы |
| GET | `/assignments/{assignment_id}/submission/mine` | Свой статус, версии и отзывы |

Попытка теста считается завершённой для прогресса только при достижении
проходного процента. Неуспешная отправка получает результат, но обязательную
проверку не завершает. Практическая работа засчитывается после решения
`accepted`; `revision_required` возвращает обучающегося к новой версии и не
завершает работу.

### Проверка работ и назначения преподавателей

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/teaching` | Курсы и задания, доступные преподавателю |
| GET | `/courses/{course_id}/assignments` | Задания курса для проверки |
| GET | `/assignments/{assignment_id}/submissions` | Отправленные работы и история |
| POST | `/submissions/{submission_id}/start-review` | Взять отправку в проверку |
| POST | `/submissions/{submission_id}/review` | Принять или вернуть с оценкой/комментарием |
| GET | `/courses/{course_id}/instructors` | Список назначенных преподавателей |
| POST | `/courses/{course_id}/instructors` | Назначить преподавателя |
| DELETE | `/courses/{course_id}/instructors/{instructor_id}` | Снять назначение без удаления отзывов |

Решение содержит `decision` (`accepted` или `revision_required`), `score` и
`comment`. Каждая отправка имеет неизменяемый номер версии, а решение связано
с проверенной версией и reviewer. Автор назначает преподавателей собственного
курса; администратор может управлять всеми назначениями. Автор не может
проверять собственную работу обучающегося на своём курсе.

### Прогресс курса с проверками

`CourseProgress` сохраняет уроки и дополняется
`total_required_assessments` / `completed_required_assessments`.
`progress_percent = floor((completed_lessons + completed_required_assessments)
* 100 / (total_lessons + total_published_required_assessments))`. Если
учитываемых элементов нет, процент равен нулю, курс не завершён. Необязательные
и архивированные проверки исключены из расчёта. Изменения уроков, публикации,
архивации, успешной попытки или принятия задания синхронизируют прогресс и
`completed_at` в одной транзакции. Полная структура ответов описана OpenAPI в
`/openapi.json`.

## Сертификаты

### POST /api/v1/certificates/issue

Требует `certificates:issue_self`. Тело: `{ "enrollment_id": "<uuid>" }`.
Успешный запрос возвращает snapshot сертификата. Если курс не завершён,
возвращается `409 course_not_completed`; запрос идемпотентен в рамках записи.

### GET /api/v1/certificates/me

Требует `certificates:read_self`. Возвращает только сертификаты текущего
пользователя и не возвращает storage key.

### GET /api/v1/certificates/{certificate_id}/download

Требует `certificates:read_self` и владение сертификатом. Ответ — приватный
`application/pdf` с `Cache-Control: private, no-store`; чужой или отсутствующий
сертификат возвращает 404.

### GET /api/v1/certificates/verify/{verification_code}

Публичный endpoint без авторизации. При успехе возвращает только `valid`,
`recipient_name`, `course_title`, `certificate_number` и `issued_at`. Неизвестный
код возвращает `404 certificate_not_found`.

Подробности о выдаче, модели и настройках PDF — в
[`certificates.md`](certificates.md).

## Корпоративное обучение (Sprint 8, этап 4)

Корпоративные операции требуют JWT. Управляющие операции доступны активным
`owner`, `admin` и `manager` только в пределах своей организации; сотрудник
видит только собственные назначения. Системная роль `organization_manager` не
даёт доступа к чужим организациям.

Элемент ответа `/members` содержит `can_update_role` и `can_remove`. Это
вычисленные для текущего пользователя scoped-права на конкретного участника;
интерфейс использует их, чтобы скрывать недоступные действия. Backend повторно
проверяет полномочия при каждой операции.

### POST /api/v1/organizations/{organization_id}/assignments

Массово создаёт назначения для 1–500 активных участников с ролью `employee`.
Курс должен быть опубликован и относиться к активной категории. Все записи
создаются одной транзакцией; если хотя бы один получатель недоступен или уже
имеет активное назначение на этот курс, запрос отклоняется целиком.

```json
{
  "course_id": "<uuid>",
  "membership_ids": ["<membership-uuid>"],
  "due_at": null,
  "is_required": true
}
```

Возвращает массив назначений со статусом `pending`. Повторное назначение после
`declined` или `cancelled` создаёт новый номер цикла; `pending` и `accepted`
дублировать нельзя.

### GET /api/v1/organizations/{organization_id}/assignments

Возвращает назначения организации со статусом и, если назначение принято,
состоянием связанного Enrollment и актуальным процентом прогресса. Для
сотрудника список ограничен его membership.

### POST /api/v1/organizations/{organization_id}/assignments/{assignment_id}/accept

Сотрудник принимает только своё назначение в состоянии `pending`. В одной
транзакции назначение становится `accepted`, а learning создаёт или реактивирует
существующий Enrollment. Повторное принятие возвращает `409
assignment_not_pending`.

### POST /api/v1/organizations/{organization_id}/assignments/{assignment_id}/decline

Сотрудник отклоняет своё ожидающее назначение. Enrollment не создаётся.

### DELETE /api/v1/organizations/{organization_id}/assignments/{assignment_id}

Владелец, администратор или менеджер отменяет назначение со статусом `pending`
или `accepted`. Отмена назначения не отменяет личный Enrollment сотрудника.

### GET /api/v1/organizations/{organization_id}/learning-stats

Сводные значения по всем циклам назначений организации: количества назначений
по статусам, уникальные участники, активные и завершённые Enrollment и средний
прогресс. Прогресс пересчитывается существующим learning-сервисом; отдельная
копия учебных данных в модуле организаций не хранится.

Личная отмена Enrollment не меняет принятое корпоративное назначение. Повторная
запись реактивирует тот же Enrollment и сохраняет историю. Активный Enrollment
продолжает обучение после архивации курса; новые назначения и Enrollment для
архивированного курса запрещены.

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

| Роль | Разрешения (коды) | Всего |
| --- | --- | --- |
| `guest` | — | 0 |
| `user` | базовые разрешения Sprint 4 + `assessments:attempt`, `assessments:read_own_results`, `assessments:submit` | 13 |
| `course_author` | базовые разрешения курса + `assessments:manage_own`, `assessments:publish_own`, `assessments:instructors_manage`, `assessments:attempt`, `assessments:read_own_results`, `assessments:submit` | 19 |
| `teacher` | разрешения обучения + `assessments:attempt`, `assessments:read_own_results`, `assessments:submit`, `assessments:review` | 14 |
| `organization_employee` | базовые разрешения обучения + `assessments:attempt`, `assessments:read_own_results`, `assessments:submit` | 13 |
| `organization_manager` | разрешения организации и обучения + `assessments:attempt`, `assessments:read_own_results`, `assessments:submit` | 16 |
| `admin` | все разрешения, включая `assessments:manage_all` | 32 |

Несколько ролей объединяются: пользователь получает объединение разрешений.
`guest` не назначается аккаунтам. Публичного API назначения ролей нет;
`course_author` назначается через CLI `python -m app.cli assign-role`.
Всего в системе 32 уникальных разрешения. Легаси-коды `learning:enroll` и
`learning:participate` сохранены для совместимости, но новые проверки обучения
используют `enrollments:*` / `progress:*`.

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

# запись на курс
$enrollment = Invoke-RestMethod -Method Post -Uri "$base/learning/enrollments" -Headers $headers `
  -ContentType "application/json" -Body (@{ course_id = $draft.id } | ConvertTo-Json)

# отметить урок завершённым
Invoke-RestMethod -Method Put `
  -Uri "$base/learning/enrollments/$($enrollment.id)/lessons/<lesson_id>/progress" `
  -Headers $headers -ContentType "application/json" -Body (@{ state = "completed" } | ConvertTo-Json)

# моё обучение
Invoke-RestMethod -Uri "$base/learning/enrollments/mine" -Headers $headers
```

## Версионирование

Все эндпоинты находятся под `/api/v1`. При несовместимых изменениях вводится
`/api/v2`; старый префикс сохраняется на время миграции клиентов.

## Notifications (Sprint 7)

`GET /api/v1/notifications/me?page=1&page_size=20&unread_only=false` возвращает уведомления текущего пользователя, общее количество, число непрочитанных и данные страницы. `GET /api/v1/notifications/unread-count` возвращает `{ "unread_count": number }`. `PATCH /api/v1/notifications/{notification_id}/read` отмечает своё уведомление прочитанным (повторный вызов безопасен); `POST /api/v1/notifications/read-all` отмечает все непрочитанные и возвращает `{ "updated": number }`. Для чужого ID возвращается 404. Чтение требует `notifications:read_own`, изменение — `notifications:update_own`. Публичных методов создания и удаления нет.

Поддерживаются типы `course_completed`, `quiz_completed`, `assignment_accepted`, `assignment_revision_required` и `certificate_issued`. Payload содержит только безопасные внутренние идентификаторы и результаты. Клиент строит разрешённые внутренние маршруты самостоятельно и не использует URL из payload.

## Administration and organizations (Sprint 8 closeout)

Платформенные endpoint `/admin/*` требуют глобальное разрешение
`admin:manage_platform`. `GET /admin/overview` возвращает фактические счётчики
пользователей, организаций, курсов, назначений и прогресса. `GET /admin/users`
и `GET /admin/courses` поддерживают `q`, `page`, `page_size`; `PATCH
/admin/users/{user_id}` меняет только `is_active` и защищает текущего и
последнего активного администратора; `POST /admin/courses/{course_id}/archive`
архивирует курс штатным сервисом обучения. `GET /admin/organizations` выводит
организации с числом активных участников.

Одноуровневые подразделения организации: `GET/POST
/organizations/{organization_id}/departments`, `PATCH/DELETE
/organizations/{organization_id}/departments/{department_id}` и
`PATCH /organizations/{organization_id}/members/{membership_id}/department`
с JSON `{"department_id":"<uuid>"}` или `null`. Создание, переименование и
удаление доступны Owner/Admin; назначение участника подразделению —
Owner/Admin/Manager. Композитный FK вместе с проверкой сервиса запрещает
привязать членство к подразделению другой организации. Удаление подразделения
снимает привязку, не удаляя участников.

Corporate assignment API включает `department_id` и `overdue_at`. Периодическая
Celery-задача проставляет `overdue_at` принятым, просроченным и незавершённым
назначениям; повторный запуск идемпотентен. Worker и Celery Beat запускаются
в Linux-контейнерах из `docker-compose.server.yml`.
