import { useEffect, useState } from 'react';

import {
  getOwnSubmission,
  quizHistory,
  saveAssignmentDraft,
  saveQuizAnswers,
  startQuiz,
  submitAssignment,
  submitQuiz,
  type AttemptResult,
  type QuizAttempt,
  type Submission,
} from '../../services/assessmentService';
import type { LearningAssignment, LearningQuiz } from '../../types/api';

export function AssessmentActivities({
  quizzes,
  assignments,
  token,
  onComplete,
}: {
  quizzes: LearningQuiz[];
  assignments: LearningAssignment[];
  token: string;
  onComplete: () => void;
}) {
  return (
    <div className="assessment-activities stack">
      {quizzes.map((quiz) => <QuizActivity key={quiz.id} quiz={quiz} token={token} onComplete={onComplete} />)}
      {assignments.map((assignment) => <AssignmentActivity key={assignment.id} assignment={assignment} token={token} onComplete={onComplete} />)}
    </div>
  );
}

function QuizActivity({ quiz, token, onComplete }: { quiz: LearningQuiz; token: string; onComplete: () => void }) {
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [history, setHistory] = useState<AttemptResult[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = (): void => { void quizHistory(token, quiz.id).then(setHistory).catch(() => undefined); };
  useEffect(refresh, [token, quiz.id]);

  const start = async (): Promise<void> => {
    setBusy(true); setError('');
    try { setAttempt(await startQuiz(token, quiz.id)); setAnswers({}); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось начать тест.'); }
    finally { setBusy(false); }
  };

  const submit = async (): Promise<void> => {
    if (!attempt) return;
    setBusy(true); setError('');
    try {
      await saveQuizAnswers(token, attempt.id, Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer })));
      await submitQuiz(token, attempt.id);
      setAttempt(null); refresh(); onComplete();
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось отправить ответы.'); }
    finally { setBusy(false); }
  };

  return (
    <article className="assessment-card card stack">
      <div className="assessment-card__heading">
        <div><p className="eyebrow">Тест{quiz.is_required ? ' · обязательный' : ''}</p><h3>{quiz.title}</h3></div>
        <span className="badge">Проходной балл {quiz.passing_score_percent}%</span>
      </div>
      {quiz.description && <p className="muted">{quiz.description}</p>}
      {error && <p className="alert alert--error" role="alert">{error}</p>}
      {attempt ? (
        <div className="stack">
          {attempt.questions.map((question, index) => (
            <fieldset className="assessment-question" key={question.id}>
              <legend>{index + 1}. {question.prompt} <span className="muted">({question.points} б.)</span></legend>
              {question.question_type === 'short_text' ? (
                <input className="field__input" aria-label="Краткий ответ" value={String(answers[question.id] ?? '')} onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })} />
              ) : question.question_type === 'true_false' ? (
                <div className="badge-row">{[true, false].map((value) => <label className="assessment-option" key={String(value)}><input type="radio" name={question.id} checked={answers[question.id] === value} onChange={() => setAnswers({ ...answers, [question.id]: value })} />{value ? 'Верно' : 'Неверно'}</label>)}</div>
              ) : question.options.map((option) => {
                const multiple = question.question_type === 'multiple_choice';
                const selected = multiple ? (Array.isArray(answers[question.id]) ? answers[question.id] as string[] : []).includes(option.id) : answers[question.id] === option.id;
                return <label className="assessment-option" key={option.id}><input type={multiple ? 'checkbox' : 'radio'} name={question.id} checked={selected} onChange={() => {
                  if (multiple) {
                    const current = Array.isArray(answers[question.id]) ? answers[question.id] as string[] : [];
                    setAnswers({ ...answers, [question.id]: selected ? current.filter((id) => id !== option.id) : [...current, option.id] });
                  } else setAnswers({ ...answers, [question.id]: option.id });
                }} />{option.text}</label>;
              })}
            </fieldset>
          ))}
          <button type="button" className="button button--primary" onClick={() => void submit()} disabled={busy}>{busy ? 'Проверка…' : 'Завершить тест'}</button>
        </div>
      ) : (
        <button type="button" className="button button--primary" onClick={() => void start()} disabled={busy}>{busy ? 'Загрузка…' : 'Начать тест'}</button>
      )}
      {history.length > 0 && <div className="assessment-history"><strong>Попытки</strong>{history.slice().reverse().map((result) => <p key={result.id}>Попытка {result.attempt_number}: {result.score}/{result.max_score} · {result.percent}% · {result.passed ? 'пройдено' : 'не пройдено'}</p>)}</div>}
    </article>
  );
}

function AssignmentActivity({ assignment, token, onComplete }: { assignment: LearningAssignment; token: string; onComplete: () => void }) {
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { void getOwnSubmission(token, assignment.id).then((value) => {
    setSubmission(value);
    setText(value?.draft_text ?? (value?.status === 'revision_required' ? value.versions.at(-1)?.response_text ?? '' : ''));
  }).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Не удалось загрузить работу.')); }, [token, assignment.id]);

  const save = async (send: boolean): Promise<void> => {
    setBusy(true); setError('');
    try {
      await saveAssignmentDraft(token, assignment.id, text);
      const updated = send ? await submitAssignment(token, assignment.id) : await getOwnSubmission(token, assignment.id);
      setSubmission(updated); onComplete();
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось сохранить работу.'); }
    finally { setBusy(false); }
  };

  const editable = !submission || submission.status === 'draft' || submission.status === 'revision_required';
  return (
    <article className="assessment-card card stack">
      <div className="assessment-card__heading"><div><p className="eyebrow">Практическое задание{assignment.is_required ? ' · обязательное' : ''}</p><h3>{assignment.title}</h3></div><span className="badge">До {assignment.max_points} баллов</span></div>
      <p>{assignment.description}</p>{assignment.requirements && <p className="muted">{assignment.requirements}</p>}
      {error && <p className="alert alert--error" role="alert">{error}</p>}
      {editable ? <>
        <label className="field"><span>Ваш ответ</span><textarea className="field__input assessment-response" value={text} onChange={(event) => setText(event.target.value)} /></label>
        <div className="badge-row"><button type="button" className="button button--ghost" onClick={() => void save(false)} disabled={busy || !text.trim()}>Сохранить черновик</button><button type="button" className="button button--primary" onClick={() => void save(true)} disabled={busy || !text.trim()}>{busy ? 'Отправка…' : 'Отправить на проверку'}</button></div>
      </> : <p className="alert alert--success">Статус: {submission?.status} · оценка {submission?.current_score ?? 'ожидается'}</p>}
      {submission?.reviews.map((review) => <div className="assessment-review" key={review.id}><strong>{review.decision === 'accepted' ? 'Работа принята' : 'Нужна доработка'} · {review.score} баллов</strong>{review.comment && <p>{review.comment}</p>}</div>)}
    </article>
  );
}
