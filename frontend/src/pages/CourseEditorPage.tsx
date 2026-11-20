import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import {
  CourseFields,
  courseFormFromValues,
  type CourseFormValues,
} from '../components/course/CourseFields';
import { CourseStructure } from '../components/course/CourseStructure';
import {
  archiveCourse,
  deleteCourse,
  getCourse,
  publishCourse,
  unpublishCourse,
  updateCourse,
} from '../services/courseService';
import { listCategories } from '../services/catalogService';
import type { Category, CourseDetail } from '../types/api';
import {
  describeCourseError,
  publishMissingFields,
} from '../utils/courseErrors';
import { courseStatusLabel, formatDate } from '../utils/labels';
import '../styles/editor.css';

export function CourseEditorPage() {
  const { courseId = '' } = useParams<{ courseId: string }>();
  const { token, user } = useAuth();
  const navigate = useNavigate();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [values, setValues] = useState<CourseFormValues | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [missing, setMissing] = useState<string[]>([]);

  useEffect(() => {
    if (token === null) {
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    Promise.all([
      getCourse(token, courseId, controller.signal),
      listCategories(controller.signal),
    ])
      .then(([loadedCourse, loadedCategories]) => {
        setCourse(loadedCourse);
        setCategories(loadedCategories);
        setValues(courseFormFromValues(loadedCourse));
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(describeCourseError(caught));
        setLoading(false);
      });

    return () => controller.abort();
  }, [token, courseId]);

  const applyCourse = (next: CourseDetail): void => {
    setCourse(next);
    setValues(courseFormFromValues(next));
  };

  const handleSave = async (): Promise<void> => {
    if (token === null || values === null) {
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateCourse(token, courseId, {
        title: values.title.trim(),
        short_description: values.short_description.trim(),
        description: values.description.trim(),
        cover_image_url: values.cover_image_url.trim() || null,
        level: values.level,
        language: values.language.trim().toLowerCase(),
        category_id: values.category_id,
      });
      applyCourse(updated);
      setNotice('Изменения сохранены.');
    } catch (caught) {
      setError(describeCourseError(caught));
    } finally {
      setSaving(false);
    }
  };

  const runStatusAction = async (
    action: 'publish' | 'unpublish' | 'archive',
  ): Promise<void> => {
    if (token === null) {
      return;
    }
    setActionBusy(true);
    setError(null);
    setNotice(null);
    setMissing([]);
    try {
      const updated =
        action === 'publish'
          ? await publishCourse(token, courseId)
          : action === 'unpublish'
            ? await unpublishCourse(token, courseId)
            : await archiveCourse(token, courseId);
      applyCourse(updated);
      setNotice(
        action === 'publish'
          ? 'Курс опубликован и появился в каталоге.'
          : action === 'unpublish'
            ? 'Курс возвращён в черновики и скрыт из каталога.'
            : 'Курс перемещён в архив и скрыт из каталога.',
      );
    } catch (caught) {
      setError(describeCourseError(caught));
      setMissing(publishMissingFields(caught));
    } finally {
      setActionBusy(false);
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (token === null || course === null) {
      return;
    }
    if (!window.confirm(`Удалить курс «${course.title}» безвозвратно?`)) {
      return;
    }
    setActionBusy(true);
    setError(null);
    try {
      await deleteCourse(token, courseId);
      navigate('/author', { replace: true });
    } catch (caught) {
      setError(describeCourseError(caught));
      setActionBusy(false);
    }
  };

  if (loading) {
    return (
      <main className="page page--centered">
        <p className="page__status" role="status">
          Загрузка курса…
        </p>
      </main>
    );
  }

  if (token === null || course === null || values === null) {
    return (
      <main className="page page--centered">
        <div className="card stack">
          <h1 className="page__title">Курс недоступен</h1>
          <p className="muted">{error ?? 'Не удалось загрузить курс.'}</p>
          <Link className="button button--ghost" to="/author">
            Вернуться к моим курсам
          </Link>
        </div>
      </main>
    );
  }

  const categoryOptions = categories.some((item) => item.id === course.category.id)
    ? categories
    : [
        ...categories,
        {
          id: course.category.id,
          name: `${course.category.name} (отключена)`,
          slug: course.category.slug,
          description: null,
          is_active: false,
          created_at: course.created_at,
          updated_at: course.updated_at,
        },
      ];

  const canDelete = user?.permissions.includes('courses:delete') ?? false;

  return (
    <main className="page editor-page">
      <header className="editor-page__header">
        <div>
          <Link className="course-page__back" to="/author">
            ← Мои курсы
          </Link>
          <div className="badge-row">
            <span className={`badge badge--status badge--status-${course.status}`}>
              {courseStatusLabel(course.status)}
            </span>
            <span className="badge">{course.category.name}</span>
            <span className="badge">Slug: {course.slug}</span>
          </div>
          <h1 className="page__title">{course.title}</h1>
          <p className="muted">
            Создан {formatDate(course.created_at)}
            {course.published_at !== null && ` · опубликован ${formatDate(course.published_at)}`}
          </p>
        </div>

        <div className="badge-row">
          <Link className="button button--ghost" to={`/author/courses/${course.id}/assessments`}>
            Тесты и задания
          </Link>
          <Link className="button button--ghost" to={`/author/courses/${course.id}/preview`}>
            Предпросмотр
          </Link>
          {course.status === 'published' && (
            <Link className="button button--ghost" to={`/catalog/${course.slug}`}>
              Публичная страница
            </Link>
          )}
        </div>
      </header>

      {error !== null && (
        <div className="alert alert--error" role="alert">
          <p>{error}</p>
          {missing.length > 0 && (
            <ul className="editor-missing">
              {missing.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {notice !== null && (
        <p className="alert alert--success" role="status">
          {notice}
        </p>
      )}

      <section className="card stack editor-status" aria-labelledby="status-title">
        <div>
          <h2 id="status-title">Публикация</h2>
          <p className="muted">
            Проверка обязательных полей и структуры выполняется на сервере. Slug после
            создания не меняется.
          </p>
        </div>
        <div className="editor-actions">
          {course.status !== 'published' && (
            <button
              type="button"
              className="button button--primary"
              onClick={() => void runStatusAction('publish')}
              disabled={actionBusy}
            >
              {actionBusy ? 'Подождите…' : 'Опубликовать'}
            </button>
          )}
          {course.status === 'published' && (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => void runStatusAction('unpublish')}
              disabled={actionBusy}
            >
              Вернуть в черновики
            </button>
          )}
          {course.status !== 'archived' && (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => void runStatusAction('archive')}
              disabled={actionBusy}
            >
              Архивировать
            </button>
          )}
          {course.status === 'archived' && (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => void runStatusAction('unpublish')}
              disabled={actionBusy}
            >
              Вернуть из архива в черновик
            </button>
          )}
        </div>
      </section>

      <section className="card stack" aria-labelledby="meta-title">
        <h2 id="meta-title">Основная информация</h2>
        <CourseFields
          values={values}
          categories={categoryOptions}
          disabled={saving}
          onChange={setValues}
          idPrefix="edit-course"
        />
        <div className="editor-actions">
          <button
            type="button"
            className="button button--primary"
            onClick={() => void handleSave()}
            disabled={saving}
          >
            {saving ? 'Сохранение…' : 'Сохранить изменения'}
          </button>
        </div>
      </section>

      <CourseStructure
        token={token}
        course={course}
        onChange={applyCourse}
        onError={setError}
      />

      {canDelete && (
        <section className="card stack editor-danger" aria-labelledby="danger-title">
          <h2 id="danger-title">Удаление</h2>
          <p className="muted">
            Обычно курс достаточно архивировать: он исчезнет из каталога, но сохранит данные.
            Удаление необратимо и вместе с курсом удаляет модули и уроки.
          </p>
          <button
            type="button"
            className="button button--danger"
            onClick={() => void handleDelete()}
            disabled={actionBusy}
          >
            Удалить курс навсегда
          </button>
        </section>
      )}
    </main>
  );
}
