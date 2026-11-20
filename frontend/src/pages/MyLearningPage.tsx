/** "Моё обучение": every enrollment with live progress. */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { ProgressBar } from '../components/learning/ProgressBar';
import {
  cancelEnrollment,
  enroll,
  listMyEnrollments,
} from '../services/learningService';
import type { Enrollment, EnrollmentPage } from '../types/api';
import { describeLearningError } from '../utils/learningErrors';
import { issueCertificate } from '../services/certificateService';
import {
  courseLevelLabel,
  formatDate,
} from '../utils/labels';
import '../styles/learning.css';

const PAGE_SIZE = 12;

function EnrollmentCard({
  enrollment,
  busy,
  onCancel,
  onReactivate,
  onCertificate,
}: {
  enrollment: Enrollment;
  busy: boolean;
  onCancel: (enrollment: Enrollment) => void;
  onReactivate: (enrollment: Enrollment) => void;
  onCertificate: (enrollment: Enrollment) => void;
}) {
  const { course, progress } = enrollment;
  const active = enrollment.status === 'active';

  return (
    <li className={`learning-card${active ? '' : ' learning-card--cancelled'}`}>
      <div className="learning-card__cover" aria-hidden="true">
        {course.cover_image_url ? (
          <img src={course.cover_image_url} alt="" />
        ) : (
          <span>{course.title.charAt(0).toUpperCase()}</span>
        )}
      </div>

      <div className="learning-card__body">
        <div className="learning-card__head">
          <div className="stack learning-card__title-block">
            <div className="badge-row">
              <span className="badge">{course.category_name}</span>
              <span className="badge badge--level">{courseLevelLabel(course.level)}</span>
              {progress.is_completed && (
                <span className="badge badge--status-published">Курс завершён</span>
              )}
              {!active && <span className="badge badge--status-archived">Запись отменена</span>}
            </div>
            <h2 className="learning-card__title">
              {active ? (
                <Link to={`/learn/${course.slug}`}>{course.title}</Link>
              ) : (
                course.title
              )}
            </h2>
            <p className="muted learning-card__short">{course.short_description}</p>
          </div>
        </div>

        <p className="learning-card__author muted">
          Автор: {course.author_display_name}
        </p>

        <ProgressBar
          percent={progress.progress_percent}
          label={`Прогресс курса «${course.title}»`}
        />

        <dl className="learning-card__stats">
          <div>
            <dt>Пройдено</dt>
            <dd>
              {progress.completed_lessons} из {progress.total_lessons}
            </dd>
          </div>
          <div>
            <dt>В процессе</dt>
            <dd>{progress.in_progress_lessons}</dd>
          </div>
          <div>
            <dt>Последняя активность</dt>
            <dd>
              {formatDate(enrollment.last_activity_at ?? enrollment.enrolled_at)}
            </dd>
          </div>
          {progress.removed_lessons_count > 0 && (
            <div>
              <dt>Удалено из программы</dt>
              <dd>{progress.removed_lessons_count}</dd>
            </div>
          )}
        </dl>

        <div className="learning-card__actions">
          {active ? (
            <>
              <Link className="button button--primary button--sm" to={`/learn/${course.slug}`}>
                {progress.is_completed
                  ? 'Повторить материалы'
                  : progress.completed_lessons > 0
                    ? 'Продолжить обучение'
                    : 'Начать обучение'}
              </Link>
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={() => onCancel(enrollment)}
                disabled={busy}
              >
                {busy ? 'Отмена…' : 'Отменить запись'}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="button button--primary button--sm"
              onClick={() => onReactivate(enrollment)}
              disabled={busy}
            >
              {busy ? 'Запись…' : 'Записаться снова'}
            </button>
          )}
          <Link className="button button--ghost button--sm" to={`/catalog/${course.slug}`}>
            О курсе
          </Link>
              {progress.is_completed && active && (
                <button
                  type="button"
                  className="button button--primary button--sm"
                  onClick={() => onCertificate(enrollment)}
                  disabled={busy}
                >
                  Получить сертификат
                </button>
              )}
        </div>
      </div>
    </li>
  );
}

export function MyLearningPage() {
  const { token } = useAuth();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<EnrollmentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (token === null) {
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    listMyEnrollments(token, page, PAGE_SIZE, controller.signal)
      .then((result) => {
        setData(result);
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
  }, [token, page, refreshKey]);

  const refresh = useCallback(() => setRefreshKey((value) => value + 1), []);

  const handleCancel = async (enrollment: Enrollment): Promise<void> => {
    if (token === null) {
      return;
    }
    if (!window.confirm(`Отменить запись на курс «${enrollment.course.title}»?`)) {
      return;
    }
    setBusyId(enrollment.id);
    setError(null);
    setNotice(null);
    try {
      await cancelEnrollment(token, enrollment.id);
      setNotice('Запись отменена. Прогресс и история сохранены.');
      refresh();
    } catch (caught) {
      setError(describeLearningError(caught));
    } finally {
      setBusyId(null);
    }
  };

  const handleReactivate = async (enrollment: Enrollment): Promise<void> => {
    if (token === null) {
      return;
    }
    setBusyId(enrollment.id);
    setError(null);
    setNotice(null);
    try {
      await enroll(token, enrollment.course_id);
      setNotice('Запись возобновлена — можно продолжить с того же места.');
      refresh();
    } catch (caught) {
      setError(describeLearningError(caught));
    } finally {
      setBusyId(null);
    }
  };

  const handleCertificate = async (enrollment: Enrollment): Promise<void> => {
    if (!token) return;
    setBusyId(enrollment.id);
    setError(null);
    setNotice(null);
    try {
      await issueCertificate(token, enrollment.id);
      window.location.assign('/certificates');
    } catch (caught) {
      setError(describeLearningError(caught));
      setBusyId(null);
    }
  };

  return (
    <main className="page learning-page">
      <header className="page__heading">
        <p className="eyebrow">Личный кабинет</p>
        <h1 className="page__title">Моё обучение</h1>
        <p className="muted">
          Записи на курсы, текущий прогресс и быстрый возврат к материалам.
        </p>
      </header>

      {notice !== null && (
        <p className="alert alert--success" role="status">
          {notice}
        </p>
      )}
      {error !== null && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}

      {loading && (
        <p className="page__status" role="status">
          Загрузка обучения…
        </p>
      )}

      {!loading && data !== null && data.items.length === 0 && (
        <div className="card stack learning-empty">
          <h2>Вы пока ни на что не записаны</h2>
          <p className="muted">
            Найдите подходящий курс в каталоге и запишитесь — прогресс сохранится
            автоматически.
          </p>
          <Link className="button button--primary" to="/catalog">
            Перейти в каталог
          </Link>
        </div>
      )}

      {!loading && data !== null && data.items.length > 0 && (
        <>
          <p className="muted catalog-count" role="status">
            Всего записей: {data.total}
          </p>
          <ul className="learning-list">
            {data.items.map((enrollment) => (
              <EnrollmentCard
                key={enrollment.id}
                enrollment={enrollment}
                busy={busyId === enrollment.id}
                onCancel={handleCancel}
                onReactivate={handleReactivate}
                onCertificate={handleCertificate}
              />
            ))}
          </ul>

          {data.pages > 1 && (
            <nav className="pagination" aria-label="Страницы обучения">
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
