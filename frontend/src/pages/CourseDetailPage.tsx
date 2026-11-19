import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { getCatalogCourse } from '../services/catalogService';
import type { CatalogCourseDetail } from '../types/api';
import { describeCourseError } from '../utils/courseErrors';
import {
  courseLevelLabel,
  formatDate,
  formatDuration,
} from '../utils/labels';
import '../styles/catalog.css';

export function CourseDetailPage() {
  const { slug = '' } = useParams<{ slug: string }>();
  const [course, setCourse] = useState<CatalogCourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <main className="page course-page">
      <Link className="course-page__back" to="/catalog">
        ← Каталог
      </Link>

      <header className="course-page__header card">
        <div className="course-page__cover">
          {course.cover_image_url ? (
            <img src={course.cover_image_url} alt="" />
          ) : (
            <span aria-hidden="true">{course.title.charAt(0).toUpperCase()}</span>
          )}
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
          Материалы уроков откроются после записи на курс — модуль обучения появится в
          следующем спринте.
        </p>
      </section>
    </main>
  );
}
