import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { listMyCourses } from '../services/courseService';
import type { CoursePage } from '../types/api';
import { describeCourseError } from '../utils/courseErrors';
import {
  courseLevelLabel,
  courseStatusLabel,
  formatDate,
  formatDuration,
} from '../utils/labels';
import '../styles/editor.css';

const PAGE_SIZE = 12;

export function AuthorCoursesPage() {
  const { token } = useAuth();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CoursePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token === null) {
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    listMyCourses(token, page, PAGE_SIZE, controller.signal)
      .then((result) => {
        setData(result);
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
  }, [token, page]);

  return (
    <main className="page">
      <header className="page__heading author-hero">
        <div>
          <p className="eyebrow">Кабинет автора</p>
          <h1 className="page__title">Мои курсы</h1>
          <p className="muted">
            Черновики видны только вам. Опубликованные курсы попадают в каталог, архивные —
            скрыты, но сохраняются.
          </p>
        </div>
        <Link className="button button--primary" to="/author/courses/new">
          Создать курс
        </Link>
      </header>

      {error !== null && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}

      {loading && (
        <p className="page__status" role="status">
          Загрузка курсов…
        </p>
      )}

      {!loading && data !== null && data.items.length === 0 && (
        <div className="card stack">
          <h2>Пока нет ни одного курса</h2>
          <p className="muted">
            Создайте черновик, добавьте модули и уроки, затем опубликуйте курс — он появится
            в общем каталоге.
          </p>
          <Link className="button button--primary" to="/author/courses/new">
            Создать первый курс
          </Link>
        </div>
      )}

      {!loading && data !== null && data.items.length > 0 && (
        <>
          <ul className="author-course-list">
            {data.items.map((course) => (
              <li key={course.id} className="author-course card">
                <div className="author-course__main">
                  <div className="badge-row">
                    <span className={`badge badge--status badge--status-${course.status}`}>
                      {courseStatusLabel(course.status)}
                    </span>
                    <span className="badge">{course.category.name}</span>
                    <span className="badge">{courseLevelLabel(course.level)}</span>
                  </div>

                  <h2 className="author-course__title">
                    <Link to={`/author/courses/${course.id}`}>{course.title}</Link>
                  </h2>
                  <p className="muted author-course__short">{course.short_description}</p>

                  <p className="author-course__meta">
                    {course.modules_count} модулей · {course.lessons_count} уроков ·{' '}
                    {formatDuration(course.total_duration_minutes)}
                    {course.published_at !== null && (
                      <> · опубликован {formatDate(course.published_at)}</>
                    )}
                  </p>
                </div>

                <div className="author-course__actions">
                  <Link className="button button--ghost button--sm" to={`/author/courses/${course.id}`}>
                    Редактировать
                  </Link>
                  {course.status === 'published' && (
                    <Link className="button button--ghost button--sm" to={`/catalog/${course.slug}`}>
                      В каталоге
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>

          {data.pages > 1 && (
            <nav className="pagination" aria-label="Страницы моих курсов">
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={data.page <= 1}
              >
                Назад
              </button>
              <span className="pagination__status">
                Страница {data.page} из {data.pages}
              </span>
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={() => setPage((current) => Math.min(data.pages, current + 1))}
                disabled={data.page >= data.pages}
              >
                Вперёд
              </button>
            </nav>
          )}
        </>
      )}
    </main>
  );
}
