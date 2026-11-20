import { useEffect, useState } from 'react';

import { useAuth } from '../auth/AuthContext';
import { listSubmissions, reviewSubmission, startReview, teachingCourses, type Submission } from '../services/assessmentService';
import '../styles/assessments.css';

interface StaffCourse { id: string; title: string; assignments: { id: string; title: string; status: string; is_required: boolean }[] }

export function AssessmentReviewsPage() {
  const { token } = useAuth();
  const [courses, setCourses] = useState<StaffCourse[]>([]);
  const [courseId, setCourseId] = useState('');
  const [assignmentId, setAssignmentId] = useState('');
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [scores, setScores] = useState<Record<string, string>>({});
  const [comments, setComments] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');

  useEffect(() => {
    if (!token) return;
    void teachingCourses(token).then((items) => {
      setCourses(items); setCourseId(items[0]?.id ?? ''); setAssignmentId(items[0]?.assignments[0]?.id ?? '');
    }).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Нет доступных курсов.'));
  }, [token]);

  const load = async (id = assignmentId): Promise<void> => {
    if (!token || !id) { setSubmissions([]); return; }
    try { setSubmissions(await listSubmissions(token, id)); setError(''); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось загрузить работы.'); }
  };

  useEffect(() => { void load(); }, [token, assignmentId]);
  const selectedCourse = courses.find((item) => item.id === courseId);

  const beginReview = async (submission: Submission): Promise<void> => {
    if (!token) return;
    setBusyId(submission.id); setError('');
    try { await startReview(token, submission.id); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось начать проверку.'); }
    finally { setBusyId(''); }
  };
  const decide = async (submission: Submission, decision: 'accepted' | 'revision_required'): Promise<void> => {
    if (!token) return;
    setBusyId(submission.id); setError('');
    try {
      await reviewSubmission(token, submission.id, {
        decision, score: Number(scores[submission.id] ?? 0), comment: comments[submission.id] ?? '',
      });
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось сохранить оценку.'); }
    finally { setBusyId(''); }
  };

  return (
    <main className="page assessment-authoring">
      <header className="page__heading"><div><p className="eyebrow">Кабинет преподавателя</p><h1 className="page__title">Проверка работ</h1><p className="muted">Доступны собственные курсы и курсы, на которые вы назначены.</p></div></header>
      {error && <p className="alert alert--error" role="alert">{error}</p>}
      <section className="card stack"><div className="assessment-form-grid"><label className="field"><span>Курс</span><select className="field__input" value={courseId} onChange={(event) => { const next = courses.find((item) => item.id === event.target.value); setCourseId(event.target.value); setAssignmentId(next?.assignments[0]?.id ?? ''); }}><option value="">Нет назначенных курсов</option>{courses.map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label><label className="field"><span>Задание</span><select className="field__input" value={assignmentId} onChange={(event) => setAssignmentId(event.target.value)}><option value="">Выберите задание</option>{selectedCourse?.assignments.map((item) => <option key={item.id} value={item.id}>{item.title} ({item.status})</option>)}</select></label></div>
        {submissions.length === 0 ? <p className="muted">Отправленных работ пока нет.</p> : submissions.map((submission) => {
          const latest = submission.versions.at(-1);
          return <article className="assessment-review-card stack" key={submission.id}><div className="assessment-card__heading"><div><h2>Работа обучающегося</h2><p className="muted">Пользователь {submission.user_id} · версия {submission.latest_version}</p></div><span className="badge">{submission.status}</span></div>
            {latest && <pre className="assessment-answer">{latest.response_text}</pre>}
            {submission.reviews.map((review) => <div className="assessment-review" key={review.id}><strong>{review.decision === 'accepted' ? 'Принята' : 'Возвращена'} · {review.score} баллов</strong>{review.comment && <p>{review.comment}</p>}</div>)}
            {submission.status === 'submitted' && <button className="button button--primary" disabled={busyId === submission.id} onClick={() => void beginReview(submission)}>{busyId === submission.id ? 'Загрузка…' : 'Начать проверку'}</button>}
            {submission.status === 'under_review' && <><label className="field"><span>Баллы</span><input className="field__input" type="number" min="0" step="0.01" value={scores[submission.id] ?? ''} onChange={(event) => setScores({ ...scores, [submission.id]: event.target.value })} /></label><label className="field"><span>Комментарий</span><textarea className="field__input" value={comments[submission.id] ?? ''} onChange={(event) => setComments({ ...comments, [submission.id]: event.target.value })} /></label><div className="badge-row"><button className="button button--primary" disabled={busyId === submission.id} onClick={() => void decide(submission, 'accepted')}>Принять работу</button><button className="button button--ghost" disabled={busyId === submission.id} onClick={() => void decide(submission, 'revision_required')}>Вернуть на доработку</button></div></>}
          </article>;
        })}
      </section>
    </main>
  );
}
