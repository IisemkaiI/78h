/** Author preview: read the full programme, drafts included, without enrolling. */

import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { MarkdownContent } from '../components/learning/MarkdownContent';
import { getCourse } from '../services/courseService';
import type { CourseDetail, Lesson } from '../types/api';
import { describeCourseError } from '../utils/courseErrors';
import {
  courseLevelLabel,
  courseStatusLabel,
  formatDuration,
} from '../utils/labels';
import '../styles/learning.css';

function firstLesson(course: CourseDetail | null): Lesson | null {
  if (course === null) {
    return null;
  }
  for (const module of [...course.modules].sort((a, b) => a.position - b.position)) {
    const lessons = [...module.lessons].sort((a, b) => a.position - b.position);
    if (lessons[0] !== undefined) {
      return lessons[0];
    }
  }
  return null;
}

export function AuthorCoursePreviewPage() {
  const { courseId = '' } = useParams<{ courseId: string }>();
  const { token } = useAuth();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token === null) {
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getCourse(token, courseId, controller.signal)
      .then((result) => {
        setCourse(result);
        setSelectedId((current) => current ?? firstLesson(result)?.id ?? null);
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

  const lessons = useMemo(() => {
    if (course === null) {
      return [];
    }
    return [...course.modules]
      .sort((a, b) => a.position - b.position)
      .flatMap((module) =>
        [...module.lessons]
          .sort((a, b) => a.position - b.position)
          .map((lesson) => ({ lesson, moduleTitle: module.title })),
      );
  }, [course]);

  const selected = useMemo(
    () => lessons.find((item) => item.lesson.id === selectedId) ?? null,
    [lessons, selectedId],
  );

  if (loading) {
    return (
      <main className="page page--centered">
        <p className="page__status" role="status">
          Загрузка предпросмотра…
        </p>
      </main>
    );
  }

  if (error !== null || course === null) {
    return (
      <main className="page page--centered">
        <div className="card stack" style={{ maxWidth: '32rem' }}>
          <p className="eyebrow">Предпросмотр недоступен</p>
          <h1 className="page__title">Не удалось открыть курс</h1>
          <p className="muted">{error ?? 'Курс не найден.'}</p>
          <Link className="button button--ghost" to="/author">
            Мои курсы
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="page learn-page">
      <header className="card stack learn-header">
        <div className="learn-header__top">
          <div className="stack">
            <p className="eyebrow">Предпросмотр автора</p>
            <h1 className="learn-header__title">{course.title}</h1>
            <div className="badge-row">
              <span className={`badge badge--status-${course.status}`}>
                {courseStatusLabel(course.status)}
              </span>
              <span className="badge">{course.category.name}</span>
              <span className="badge badge--level">{courseLevelLabel(course.level)}</span>
              <span className="badge">Язык: {course.language}</span>
            </div>
          </div>
          <div className="badge-row learn-header__actions">
            <Link
              className="button button--ghost button--sm"
              to={`/author/courses/${course.id}`}
            >
              Редактировать курс
            </Link>
            <Link className="button button--ghost button--sm" to="/author">
              Мои курсы
            </Link>
          </div>
        </div>
        <p className="alert alert--info">
          Так материалы увидят обучающиеся. Черновик доступен только автору и администраторам.
        </p>
      </header>

      <div className="learn-layout">
        <aside className="card learn-sidebar" aria-label="Программа курса">
          <h2 className="learn-sidebar__title">Программа</h2>
          {lessons.length === 0 ? (
            <p className="muted">В курсе пока нет уроков.</p>
          ) : (
            <ol className="learn-program">
              {course.modules
                .slice()
                .sort((a, b) => a.position - b.position)
                .map((module) => (
                  <li key={module.id} className="learn-program__module">
                    <p className="learn-program__module-title">
                      <span className="program__position">{module.position}</span>
                      {module.title}
                    </p>
                    <ol className="learn-program__lessons">
                      {module.lessons
                        .slice()
                        .sort((a, b) => a.position - b.position)
                        .map((lesson) => (
                          <li key={lesson.id}>
                            <button
                              type="button"
                              className={`learn-program__lesson learn-program__lesson--button${
                                lesson.id === selectedId
                                  ? ' learn-program__lesson--active'
                                  : ''
                              }`}
                              onClick={() => setSelectedId(lesson.id)}
                            >
                              <span className="learn-program__lesson-title">{lesson.title}</span>
                            </button>
                          </li>
                        ))}
                    </ol>
                  </li>
                ))}
            </ol>
          )}
        </aside>

        <section className="card stack learn-content">
          {selected === null ? (
            <p className="muted">Выберите урок в программе слева.</p>
          ) : (
            <>
              <div className="learn-content__head">
                <div className="stack">
                  <p className="eyebrow">
                    {selected.moduleTitle} ·{' '}
                    {formatDuration(selected.lesson.estimated_duration_minutes)}
                  </p>
                  <h2 className="learn-content__title">{selected.lesson.title}</h2>
                </div>
              </div>

              {selected.lesson.description !== null && (
                <p className="muted learn-content__description">
                  {selected.lesson.description}
                </p>
              )}

              {selected.lesson.content.trim().length === 0 ? (
                <p className="alert alert--info">
                  Урок пока не содержит материалов. Добавьте содержимое в редакторе.
                </p>
              ) : (
                <MarkdownContent content={selected.lesson.content} />
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
