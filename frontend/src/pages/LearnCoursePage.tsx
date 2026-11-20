/** Course player: programme, lesson content and three-state progress. */

import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { LessonStateBadge } from '../components/learning/LessonStateBadge';
import { MarkdownContent } from '../components/learning/MarkdownContent';
import { ProgressBar } from '../components/learning/ProgressBar';
import {
  getLearningCourse,
  getLearningLesson,
  setLessonState,
} from '../services/learningService';
import type {
  CourseProgress,
  LearningCourse,
  LearningLesson,
  LearningLessonContent,
  LessonProgressEntry,
  LessonState,
} from '../types/api';
import { describeLearningError } from '../utils/learningErrors';
import { formatDuration, lessonStateLabel } from '../utils/labels';
import '../styles/learning.css';

interface FlatLesson {
  lesson: LearningLesson;
  moduleTitle: string;
}

function flattenLessons(course: LearningCourse): FlatLesson[] {
  return [...course.modules]
    .sort((a, b) => a.position - b.position)
    .flatMap((module) =>
      [...module.lessons]
        .sort((a, b) => a.position - b.position)
        .map((lesson) => ({ lesson, moduleTitle: module.title })),
    );
}

export function LearnCoursePage() {
  const { slug = '', lessonId } = useParams<{ slug: string; lessonId?: string }>();
  const { token } = useAuth();

  const [course, setCourse] = useState<LearningCourse | null>(null);
  const [lesson, setLesson] = useState<LearningLessonContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [lessonLoading, setLessonLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lessonError, setLessonError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (token === null) {
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getLearningCourse(token, slug, controller.signal)
      .then((result) => {
        setCourse(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(describeLearningError(caught));
        setLoading(false);
      });

    return () => controller.abort();
  }, [token, slug]);

  useEffect(() => {
    if (token === null || lessonId === undefined) {
      setLesson(null);
      return;
    }
    const controller = new AbortController();
    setLessonLoading(true);
    setLessonError(null);
    setNotice(null);

    getLearningLesson(token, slug, lessonId, controller.signal)
      .then((result) => {
        setLesson(result);
        setLessonLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setLessonError(describeLearningError(caught));
        setLessonLoading(false);
      });

    return () => controller.abort();
  }, [token, slug, lessonId]);

  const flatLessons = useMemo(
    () => (course === null ? [] : flattenLessons(course)),
    [course],
  );

  const currentIndex = useMemo(
    () =>
      lessonId === undefined
        ? -1
        : flatLessons.findIndex((item) => item.lesson.id === lessonId),
    [flatLessons, lessonId],
  );

  const nextLesson: FlatLesson | null =
    currentIndex >= 0 && currentIndex < flatLessons.length - 1
      ? flatLessons[currentIndex + 1] ?? null
      : null;

  const applyState = (
    updated: LessonProgressEntry,
    progress: CourseProgress,
  ): void => {
    setLesson((previous) =>
      previous === null
        ? previous
        : {
            ...previous,
            state: updated.state,
            started_at: updated.started_at,
            completed_at: updated.completed_at,
          },
    );
    setCourse((previous) => {
      if (previous === null) {
        return previous;
      }
      return {
        ...previous,
        progress,
        modules: previous.modules.map((module) => ({
          ...module,
          lessons: module.lessons.map((item) =>
            item.id === updated.lesson_id
              ? {
                  ...item,
                  state: updated.state,
                  started_at: updated.started_at,
                  completed_at: updated.completed_at,
                }
              : item,
          ),
        })),
      };
    });
  };

  const updateState = async (state: LessonState): Promise<void> => {
    if (token === null || course === null || lesson === null || course.enrollment_id === null) {
      return;
    }
    setBusy(true);
    setNotice(null);
    setLessonError(null);
    try {
      const result = await setLessonState(
        token,
        course.enrollment_id,
        lesson.id,
        state,
      );
      applyState(result.lesson, result.course_progress);
      setNotice(
        state === 'completed'
          ? 'Урок отмечен как завершённый.'
          : state === 'in_progress'
            ? 'Урок возвращён в работу.'
            : 'Прогресс урока сброшен.',
      );
    } catch (caught) {
      setLessonError(describeLearningError(caught));
    } finally {
      setBusy(false);
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
        <div className="card stack" style={{ maxWidth: '32rem' }}>
          <p className="eyebrow">Обучение недоступно</p>
          <h1 className="page__title">Не удалось открыть курс</h1>
          <p className="muted">{error ?? 'Курс не найден.'}</p>
          <div className="badge-row">
            <Link className="button button--ghost" to="/my-learning">
              Моё обучение
            </Link>
            <Link className="button button--ghost" to={`/catalog/${slug}`}>
              Страница курса
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const { progress } = course;
  const completed = progress.is_completed;

  return (
    <main className="page learn-page">
      <header className="card stack learn-header">
        <div className="learn-header__top">
          <div className="stack">
            <p className="eyebrow">{course.course.category_name}</p>
            <h1 className="learn-header__title">{course.course.title}</h1>
            <p className="muted">
              {progress.completed_lessons} из {progress.total_lessons} уроков пройдено
              {progress.removed_lessons_count > 0
                ? ` · ${progress.removed_lessons_count} удалено из программы`
                : ''}
            </p>
          </div>
          <div className="badge-row learn-header__actions">
            <Link className="button button--ghost button--sm" to="/my-learning">
              Моё обучение
            </Link>
            <Link className="button button--ghost button--sm" to={`/catalog/${course.course.slug}`}>
              О курсе
            </Link>
          </div>
        </div>
        <ProgressBar percent={progress.progress_percent} />
        {completed && (
          <p className="alert alert--success" role="status">
            Курс завершён. Прогресс сохранён — материалы остаются доступными.
          </p>
        )}
      </header>

      <div className="learn-layout">
        <aside className="card learn-sidebar" aria-label="Программа курса">
          <h2 className="learn-sidebar__title">Программа</h2>
          {course.modules.length === 0 ? (
            <p className="muted">В курсе пока нет уроков.</p>
          ) : (
            <ol className="learn-program">
              {[...course.modules]
                .sort((a, b) => a.position - b.position)
                .map((module) => (
                  <li key={module.id} className="learn-program__module">
                    <p className="learn-program__module-title">
                      <span className="program__position">{module.position}</span>
                      {module.title}
                    </p>
                    <ol className="learn-program__lessons">
                      {[...module.lessons]
                        .sort((a, b) => a.position - b.position)
                        .map((item) => (
                          <li key={item.id}>
                            <Link
                              className={`learn-program__lesson${
                                item.id === lessonId ? ' learn-program__lesson--active' : ''
                              }`}
                              to={`/learn/${course.course.slug}/lessons/${item.id}`}
                            >
                              <span className="learn-program__lesson-title">{item.title}</span>
                              <span
                                className={`learn-program__dot learn-program__dot--${item.state.replace(
                                  '_',
                                  '-',
                                )}`}
                                aria-label={lessonStateLabel(item.state)}
                                title={lessonStateLabel(item.state)}
                              />
                            </Link>
                          </li>
                        ))}
                    </ol>
                  </li>
                ))}
            </ol>
          )}
        </aside>

        <section className="card stack learn-content" aria-live="polite">
          {lessonId === undefined ? (
            <div className="stack learn-overview">
              <h2>Продолжите обучение</h2>
              <p className="muted">
                Выберите урок в программе слева. Отмечайте уроки как завершённые, чтобы
                прогресс курса обновлялся автоматически.
              </p>
              {flatLessons.length > 0 && (
                <div className="badge-row">
                  {(() => {
                    const next =
                      flatLessons.find((item) => item.lesson.state !== 'completed') ??
                      flatLessons[0];
                    return next !== undefined ? (
                      <Link
                        className="button button--primary"
                        to={`/learn/${course.course.slug}/lessons/${next.lesson.id}`}
                      >
                        {next.lesson.state === 'not_started'
                          ? 'Начать первый урок'
                          : 'Продолжить с текущего урока'}
                      </Link>
                    ) : null;
                  })()}
                </div>
              )}
            </div>
          ) : lessonLoading ? (
            <p className="page__status" role="status">
              Загрузка урока…
            </p>
          ) : lessonError !== null ? (
            <p className="alert alert--error" role="alert">
              {lessonError}
            </p>
          ) : lesson === null ? (
            <p className="muted">Урок не найден.</p>
          ) : (
            <>
              <div className="learn-content__head">
                <div className="stack">
                  <p className="eyebrow">
                    {currentIndex >= 0 ? `Урок ${currentIndex + 1}` : 'Урок'} ·{' '}
                    {formatDuration(lesson.estimated_duration_minutes)}
                  </p>
                  <h2 className="learn-content__title">{lesson.title}</h2>
                </div>
                <LessonStateBadge state={lesson.state} />
              </div>

              {lesson.description !== null && (
                <p className="muted learn-content__description">{lesson.description}</p>
              )}

              {notice !== null && (
                <p className="alert alert--success" role="status">
                  {notice}
                </p>
              )}

              <MarkdownContent content={lesson.content} />

              <div className="learn-content__actions">
                {lesson.state !== 'in_progress' && lesson.state !== 'completed' && (
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => void updateState('in_progress')}
                    disabled={busy}
                  >
                    {busy ? 'Сохранение…' : 'Начать урок'}
                  </button>
                )}
                {lesson.state === 'in_progress' && (
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => void updateState('not_started')}
                    disabled={busy}
                  >
                    Сбросить прогресс
                  </button>
                )}
                {lesson.state === 'completed' ? (
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => void updateState('in_progress')}
                    disabled={busy}
                  >
                    {busy ? 'Сохранение…' : 'Вернуть в работу'}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={() => void updateState('completed')}
                    disabled={busy}
                  >
                    {busy ? 'Сохранение…' : 'Завершить урок'}
                  </button>
                )}
                {nextLesson !== null && (
                  <Link
                    className="button button--ghost"
                    to={`/learn/${course.course.slug}/lessons/${nextLesson.lesson.id}`}
                  >
                    Следующий урок →
                  </Link>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
