import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { ProgressBar } from '../components/learning/ProgressBar';
import { CourseCover } from '../components/course/CourseCover';
import { getCatalogCourse } from '../services/catalogService';
import { enroll, getEnrollmentStatus } from '../services/learningService';
import type { CatalogCourseDetail, Enrollment } from '../types/api';
import { describeCourseError } from '../utils/courseErrors';
import { describeLearningError } from '../utils/learningErrors';
import {
  courseLevelLabel,
  formatDate,
  formatDuration,
} from '../utils/labels';
import '../styles/catalog.css';
import '../styles/learning.css';

export function CourseDetailPage() {
  const { slug = '' } = useParams<{ slug: string }>();
  const { status: authStatus, token, user } = useAuth();
  const navigate = useNavigate();

  const [course, setCourse] = useState<CatalogCourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [enrollmentLoading, setEnrollmentLoading] = useState(false);
  const [enrollBusy, setEnrollBusy] = useState(false);
  const [enrollError, setEnrollError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canReadOwn = user?.permissions.includes('enrollments:read_own') ?? false;
  const canEnroll = user?.permissions.includes('enrollments:create') ?? false;
  const isAuthor = user !== null && course !== null && course.author.id === user.id;
  const activeEnrollment = enrollment?.status === 'active' ? enrollment : null;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getCatalogCourse(slug, controller.signal)
      .then((result) => {
        setCourse(result);
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
  }, [slug]);

  useEffect(() => {
    if (token === null || course === null || !canReadOwn || isAuthor) {
      setEnrollment(null);
      return;
    }
    const controller = new AbortController();
    setEnrollmentLoading(true);
    setEnrollError(null);

    getEnrollmentStatus(token, course.id, controller.signal)
      .then((result) => {
        setEnrollment(result.enrollment);
        setEnrollmentLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setEnrollError(describeLearningError(caught));
        setEnrollmentLoading(false);
      });

    return () => controller.abort();
  }, [token, course, canReadOwn, isAuthor]);

  const handleEnroll = async (): Promise<void> => {
    if (token === null || course === null) {
      return;
    }
    setEnrollBusy(true);
    setEnrollError(null);
    setNotice(null);
    try {
      const result = await enroll(token, course.id);
      setEnrollment(result);
      setNotice(
        result.progress.completed_lessons > 0
          ? 'Запись возобновлена. Прогресс сохранён — продолжайте с того же места.'
          : 'Вы записаны на курс. Можно приступать к первому уроку.',
      );
      navigate(`/learn/${course.slug}`);
    } catch (caught) {
      setEnrollError(describeLearningError(caught));
    } finally {
      setEnrollBusy(false);
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

  if (error !== null || course === null) {
    return (
      <main className="page page--centered">
        <div className="card stack">
          <p className="eyebrow">Курс недоступен</p>
          <h1 className="page__title">Курс не найден</h1>
          <p className="muted">
            {error ?? 'Возможно, курс ещё не опубликован или перенесён в архив.'}
          </p>
          <Link className="button button--ghost" to="/catalog">
            Вернуться в каталог
          </Link>
        </div>
      </main>
    );
  }

  const enrollmentPanel = (() => {
    if (isAuthor) {
      return (
        <div className="enroll-panel stack">
          <p className="eyebrow">Ваш курс</p>
          <p className="muted">
            Автор не может записаться на собственный курс. Проверьте материалы в режиме
            предпросмотра.
          </p>
          <div className="badge-row">
            <Link className="button button--ghost" to={`/author/courses/${course.id}/preview`}>
              Предпросмотр
            </Link>
            <Link className="button button--ghost" to={`/author/courses/${course.id}`}>
              Редактировать
            </Link>
          </div>
        </div>
      );
    }

    if (authStatus === 'anonymous' || token === null) {
      return (
        <div className="enroll-panel stack">
          <p className="eyebrow">Обучение</p>
          <p className="muted">
            Запишитесь на курс, чтобы открыть материалы уроков и сохранять прогресс.
          </p>
          <div className="badge-row">
            <Link
              className="button button--primary"
              to="/login"
              state={{ from: `/catalog/${course.slug}` }}
            >
              Войти и записаться
            </Link>
            <Link className="button button--ghost" to="/register">
              Регистрация
            </Link>
          </div>
        </div>
      );
    }

    if (enrollmentLoading) {
      return (
        <p className="page__status" role="status">
          Проверка записи…
        </p>
      );
    }

    if (activeEnrollment !== null) {
      return (
        <div className="enroll-panel stack">
          <div className="enroll-panel__head">
            <div>
              <p className="eyebrow">Вы записаны</p>
              <p className="muted">
                {activeEnrollment.progress.completed_lessons} из{' '}
                {activeEnrollment.progress.total_lessons} уроков пройдено
              </p>
            </div>
            {activeEnrollment.progress.is_completed && (
              <span className="badge badge--status-published">Курс завершён</span>
            )}
          </div>
          <ProgressBar percent={activeEnrollment.progress.progress_percent} />
          <div className="badge-row">
            <Link className="button button--primary" to={`/learn/${course.slug}`}>
              {activeEnrollment.progress.completed_lessons > 0
                ? 'Продолжить обучение'
                : 'Начать обучение'}
            </Link>
            <Link className="button button--ghost" to="/my-learning">
              Моё обучение
            </Link>
          </div>
        </div>
      );
    }

    if (!canEnroll) {
      return (
        <div className="enroll-panel stack">
          <p className="eyebrow">Обучение</p>
          <p className="muted">
            Запись на курсы недоступна для вашей роли. Обратитесь к администратору
            платформы.
          </p>
        </div>
      );
    }

    return (
      <div className="enroll-panel stack">
        <p className="eyebrow">
          {enrollment?.status === 'cancelled' ? 'Запись отменена' : 'Готовы начать?'}
        </p>
        <p className="muted">
          {enrollment?.status === 'cancelled'
            ? 'Прогресс сохранён. Запись можно возобновить с того же места.'
            : 'После записи откроются материалы уроков. Прогресс сохраняется автоматически.'}
        </p>
        <div className="badge-row">
          <button
            type="button"
            className="button button--primary"
            onClick={() => void handleEnroll()}
            disabled={enrollBusy}
          >
            {enrollBusy
              ? 'Запись…'
              : enrollment?.status === 'cancelled'
                ? 'Записаться снова'
                : 'Записаться на курс'}
          </button>
        </div>
      </div>
    );
  })();

  return (
    <main className="page course-page">
      <Link className="course-page__back" to="/catalog">
        ← Каталог
      </Link>

      <header className="course-page__header card">
        <div className="course-page__cover">
          <CourseCover title={course.title} slug={course.slug} category={course.category.name} imageUrl={course.cover_image_url} />
        </div>

        <div className="course-page__intro">
          <div className="badge-row">
            <span className="badge">{course.category.name}</span>
            <span className="badge badge--level">{courseLevelLabel(course.level)}</span>
            <span className="badge">Язык: {course.language}</span>
          </div>

          <h1 className="course-page__title">{course.title}</h1>
          <p className="muted course-page__short">{course.short_description}</p>

          <dl className="course-page__meta">
            <div>
              <dt>Автор</dt>
              <dd>{course.author.display_name}</dd>
            </div>
            <div>
              <dt>Модули</dt>
              <dd>{course.modules_count}</dd>
            </div>
            <div>
              <dt>Уроки</dt>
              <dd>{course.lessons_count}</dd>
            </div>
            <div>
              <dt>Длительность</dt>
              <dd>{formatDuration(course.total_duration_minutes)}</dd>
            </div>
            {course.published_at !== null && (
              <div>
                <dt>Опубликован</dt>
                <dd>{formatDate(course.published_at)}</dd>
              </div>
            )}
          </dl>
        </div>
      </header>

      <section className="card" aria-label="Запись на курс">
        {notice !== null && (
          <p className="alert alert--success" role="status">
            {notice}
          </p>
        )}
        {enrollError !== null && (
          <p className="alert alert--error" role="alert">
            {enrollError}
          </p>
        )}
        {enrollmentPanel}
      </section>

      <section className="card stack" aria-labelledby="course-description-title">
        <h2 id="course-description-title">О курсе</h2>
        <p className="course-page__description">{course.description}</p>
      </section>

      <section className="card stack" aria-labelledby="course-program-title">
        <h2 id="course-program-title">Программа</h2>

        {course.modules.length === 0 ? (
          <p className="muted">Программа курса пока не опубликована.</p>
        ) : (
          <ol className="program">
            {course.modules.map((module) => (
              <li key={module.id} className="program__module">
                <details open>
                  <summary>
                    <span className="program__position">{module.position}</span>
                    <span className="program__module-title">{module.title}</span>
                    <span className="program__count">
                      {module.lessons.length}{' '}
                      {module.lessons.length === 1 ? 'урок' : 'уроков'}
                    </span>
                  </summary>

                  {module.description !== null && (
                    <p className="muted program__description">{module.description}</p>
                  )}

                  <ol className="program__lessons">
                    {module.lessons.map((lesson) => (
                      <li key={lesson.id} className="program__lesson">
                        <span className="program__lesson-title">{lesson.title}</span>
                        <span className="program__lesson-duration">
                          {formatDuration(lesson.estimated_duration_minutes)}
                        </span>
                        {lesson.description !== null && (
                          <p className="muted program__lesson-description">
                            {lesson.description}
                          </p>
                        )}
                      </li>
                    ))}
                  </ol>
                </details>
              </li>
            ))}
          </ol>
        )}

        <p className="alert alert--info">
          {activeEnrollment !== null
            ? 'Материалы уроков открыты — переходите к обучению по кнопке выше.'
            : 'Полные материалы уроков открываются после записи на курс.'}
        </p>
      </section>
    </main>
  );
}
