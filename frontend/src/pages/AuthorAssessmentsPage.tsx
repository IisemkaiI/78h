import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { ApiError } from '../services/apiClient';
import { getCourse } from '../services/courseService';
import {
  addInstructor, createAssignment, createQuiz, listAssignments, listInstructors,
  listQuizzes, removeInstructor, setAssignmentStatus, setQuizStatus, updateAssignment,
  updateQuiz, type AuthorAssignment, type AuthorQuiz, type QuizQuestion,
} from '../services/assessmentService';
import type { CourseDetail } from '../types/api';
import '../styles/assessments.css';

interface EditableQuestion {
  question_type: QuizQuestion['question_type'];
  prompt: string;
  options: { id: string; text: string }[];
  answer: string | string[] | boolean;
  accepted: string;
  points: number;
  explanation: string;
}

const blankQuestion = (): EditableQuestion => ({
  question_type: 'single_choice', prompt: '',
  options: [{ id: 'a', text: '' }, { id: 'b', text: '' }],
  answer: 'a', accepted: '', points: 1, explanation: '',
});

function assessmentError(caught: unknown): string {
  if (caught instanceof ApiError && Array.isArray(caught.details)) {
    const details = caught.details as { location?: unknown[]; message?: string }[];
    return `${caught.message}: ${details.map((item) => `${(item.location ?? []).join('.')}: ${item.message ?? 'invalid value'}`).join('; ')}`;
  }
  return caught instanceof Error ? caught.message : 'Не удалось сохранить материал.';
}

function fromQuestion(question: QuizQuestion & { id: string }): EditableQuestion {
  return {
    question_type: question.question_type,
    prompt: question.prompt,
    options: question.options,
    answer: question.answer_key as string | string[] | boolean,
    accepted: Array.isArray(question.answer_key) ? question.answer_key.join(', ') : '',
    points: Number(question.points),
    explanation: question.explanation ?? '',
  };
}

export function AuthorAssessmentsPage() {
  const { courseId = '' } = useParams<{ courseId: string }>();
  const { token } = useAuth();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [quizzes, setQuizzes] = useState<AuthorQuiz[]>([]);
  const [assignments, setAssignments] = useState<AuthorAssignment[]>([]);
  const [instructors, setInstructors] = useState<{ instructor_id: string; display_name: string }[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [quizId, setQuizId] = useState<string | null>(null);
  const [quizTitle, setQuizTitle] = useState('Новый тест');
  const [quizDescription, setQuizDescription] = useState('');
  const [lessonId, setLessonId] = useState('');
  const [required, setRequired] = useState(false);
  const [assignmentRequired, setAssignmentRequired] = useState(false);
  const [passing, setPassing] = useState(70);
  const [timeLimit, setTimeLimit] = useState('');
  const [maxAttempts, setMaxAttempts] = useState('');
  const [questions, setQuestions] = useState<EditableQuestion[]>([blankQuestion()]);
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [assignmentTitle, setAssignmentTitle] = useState('');
  const [assignmentDescription, setAssignmentDescription] = useState('');
  const [requirements, setRequirements] = useState('');
  const [maxPoints, setMaxPoints] = useState('10');
  const [dueAt, setDueAt] = useState('');
  const [allowResubmission, setAllowResubmission] = useState(true);
  const [instructorId, setInstructorId] = useState('');

  const reload = async (): Promise<void> => {
    if (!token) return;
    const [loadedCourse, loadedQuizzes, loadedAssignments, loadedInstructors] = await Promise.all([
      getCourse(token, courseId), listQuizzes(token, courseId), listAssignments(token, courseId), listInstructors(token, courseId),
    ]);
    setCourse(loadedCourse); setQuizzes(loadedQuizzes); setAssignments(loadedAssignments); setInstructors(loadedInstructors);
    if (!lessonId && loadedCourse.modules[0]?.lessons[0]) setLessonId(loadedCourse.modules[0].lessons[0].id);
  };

  useEffect(() => { void reload().catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Не удалось загрузить материалы.')); }, [token, courseId]);

  const resetQuiz = (): void => { setQuizId(null); setQuizTitle('Новый тест'); setQuizDescription(''); setRequired(false); setPassing(70); setTimeLimit(''); setMaxAttempts(''); setQuestions([blankQuestion()]); };
  const editQuiz = (quiz: AuthorQuiz): void => { setQuizId(quiz.id); setQuizTitle(quiz.title); setQuizDescription(quiz.description ?? ''); setLessonId(quiz.lesson_id ?? ''); setRequired(quiz.is_required); setPassing(quiz.passing_score_percent); setTimeLimit(quiz.time_limit_minutes?.toString() ?? ''); setMaxAttempts(quiz.max_attempts?.toString() ?? ''); setQuestions(quiz.questions.map(fromQuestion)); };
  const questionPayload = (question: EditableQuestion, position: number): QuizQuestion => ({
    question_type: question.question_type, prompt: question.prompt,
    options: question.question_type === 'single_choice' || question.question_type === 'multiple_choice' ? question.options : [],
    answer_key: question.question_type === 'short_text'
      ? question.accepted.split(',').map((item) => item.trim()).filter(Boolean)
      : question.answer,
    points: Number(question.points), position, explanation: question.explanation || null,
  });

  const saveQuiz = async (): Promise<void> => {
    if (!token || !lessonId) { setError('Сначала выберите урок.'); return; }
    setBusy(true); setError(''); setNotice('');
    const body = {
      course_id: courseId, lesson_id: lessonId, title: quizTitle,
      description: quizDescription || null, is_required: required,
      passing_score_percent: passing, time_limit_minutes: timeLimit ? Number(timeLimit) : null,
      max_attempts: maxAttempts ? Number(maxAttempts) : null,
      questions: questions.map((question, index) => questionPayload(question, index + 1)),
    };
    try {
      if (quizId) await updateQuiz(token, quizId, { ...body, course_id: undefined, lesson_id: undefined });
      else await createQuiz(token, body);
      await reload(); resetQuiz(); setNotice('Тест сохранён.');
    } catch (caught) { setError(assessmentError(caught)); }
    finally { setBusy(false); }
  };

  const saveAssignment = async (): Promise<void> => {
    if (!token || !lessonId) { setError('Сначала выберите урок.'); return; }
    setBusy(true); setError('');
    const body = { course_id: courseId, lesson_id: lessonId, title: assignmentTitle, description: assignmentDescription, requirements: requirements || null, max_points: Number(maxPoints), due_at: dueAt ? new Date(dueAt).toISOString() : null, allow_resubmission: allowResubmission, is_required: assignmentRequired };
    try {
      if (assignmentId) await updateAssignment(token, assignmentId, { ...body, course_id: undefined, lesson_id: undefined });
      else await createAssignment(token, body);
      await reload(); setAssignmentId(null); setAssignmentTitle(''); setAssignmentDescription(''); setRequirements(''); setDueAt(''); setNotice('Практическое задание сохранено.');
    } catch (caught) { setError(assessmentError(caught)); }
    finally { setBusy(false); }
  };

  if (!course) return <main className="page"><p className="page__status">{error || 'Загрузка…'}</p></main>;
  const lessons = course.modules.flatMap((module) => module.lessons.map((lesson) => ({ ...lesson, moduleTitle: module.title })));

  return (
    <main className="page assessment-authoring">
      <header className="page__heading"><div><p className="eyebrow">Конструктор курса · Sprint 5</p><h1 className="page__title">Тесты и задания</h1><p className="muted">{course.title}</p></div><Link className="button button--ghost" to={`/author/courses/${courseId}`}>К редактору курса</Link></header>
      {error && <p className="alert alert--error" role="alert">{error}</p>}{notice && <p className="alert alert--success" role="status">{notice}</p>}
      <label className="field"><span>Урок программы</span><select className="field__input" value={lessonId} onChange={(event) => setLessonId(event.target.value)}>{lessons.map((lesson) => <option key={lesson.id} value={lesson.id}>{lesson.moduleTitle} · {lesson.title}</option>)}</select></label>

      <section className="card stack"><div className="assessment-card__heading"><h2>{quizId ? 'Редактирование теста' : 'Создать тест'}</h2>{quizId && <button className="button button--ghost button--sm" type="button" onClick={resetQuiz}>Новый тест</button>}</div>
        <div className="assessment-form-grid"><label className="field"><span>Название</span><input className="field__input" value={quizTitle} onChange={(event) => setQuizTitle(event.target.value)} /></label><label className="field"><span>Проходной процент</span><input className="field__input" type="number" min="0" max="100" value={passing} onChange={(event) => setPassing(Number(event.target.value))} /></label><label className="field"><span>Время в минутах (необязательно)</span><input className="field__input" type="number" value={timeLimit} onChange={(event) => setTimeLimit(event.target.value)} /></label><label className="field"><span>Максимум попыток (необязательно)</span><input className="field__input" type="number" value={maxAttempts} onChange={(event) => setMaxAttempts(event.target.value)} /></label></div>
        <label className="field"><span>Описание</span><textarea className="field__input" value={quizDescription} onChange={(event) => setQuizDescription(event.target.value)} /></label>
        <label className="assessment-option"><input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} />Обязательная проверка прогресса</label>
        {questions.map((question, index) => <fieldset className="assessment-question" key={index}><legend>Вопрос {index + 1}</legend>
          <div className="assessment-form-grid"><label className="field"><span>Тип</span><select className="field__input" value={question.question_type} onChange={(event) => setQuestions(questions.map((item, i) => i === index ? { ...blankQuestion(), ...item, question_type: event.target.value as EditableQuestion['question_type'], answer: event.target.value === 'true_false' ? true : item.answer } : item))}><option value="single_choice">Один вариант</option><option value="multiple_choice">Несколько вариантов</option><option value="true_false">Верно / неверно</option><option value="short_text">Краткий ответ</option></select></label><label className="field"><span>Баллы</span><input className="field__input" type="number" min="0.01" step="0.01" value={question.points} onChange={(event) => setQuestions(questions.map((item, i) => i === index ? { ...item, points: Number(event.target.value) } : item))} /></label></div>
          <label className="field"><span>Формулировка</span><textarea className="field__input" value={question.prompt} onChange={(event) => setQuestions(questions.map((item, i) => i === index ? { ...item, prompt: event.target.value } : item))} /></label>
          {(question.question_type === 'single_choice' || question.question_type === 'multiple_choice') && <div className="stack">{question.options.map((option, optionIndex) => <div className="badge-row" key={option.id}><input className="field__input" aria-label={`Вариант ${optionIndex + 1}`} value={option.text} onChange={(event) => setQuestions(questions.map((item, i) => i === index ? { ...item, options: item.options.map((entry) => entry.id === option.id ? { ...entry, text: event.target.value } : entry) } : item))} /><label className="assessment-option"><input type={question.question_type === 'multiple_choice' ? 'checkbox' : 'radio'} name={`correct-${index}`} checked={Array.isArray(question.answer) ? question.answer.includes(option.id) : question.answer === option.id} onChange={() => setQuestions(questions.map((item, i) => i === index ? { ...item, answer: question.question_type === 'multiple_choice' ? (Array.isArray(item.answer) ? item.answer.includes(option.id) ? item.answer.filter((id) => id !== option.id) : [...item.answer, option.id] : [option.id]) : option.id } : item))} />Верный</label><button className="button button--ghost button--sm" type="button" onClick={() => setQuestions(questions.map((item, i) => i === index ? { ...item, options: item.options.filter((entry) => entry.id !== option.id) } : item))}>Удалить</button></div>)}<button className="button button--ghost button--sm" type="button" onClick={() => setQuestions(questions.map((item, i) => i === index ? { ...item, options: [...item.options, { id: `o${Date.now()}`, text: '' }] } : item))}>Добавить вариант</button></div>}
          {question.question_type === 'true_false' && <label className="assessment-option"><input type="checkbox" checked={question.answer === true} onChange={(event) => setQuestions(questions.map((item, i) => i === index ? { ...item, answer: event.target.checked } : item))} />Правильный ответ: верно</label>}
          {question.question_type === 'short_text' && <label className="field"><span>Допустимые ответы (через запятую)</span><input className="field__input" value={question.accepted} onChange={(event) => setQuestions(questions.map((item, i) => i === index ? { ...item, accepted: event.target.value } : item))} /></label>}
          <label className="field"><span>Пояснение после проверки</span><textarea className="field__input" value={question.explanation} onChange={(event) => setQuestions(questions.map((item, i) => i === index ? { ...item, explanation: event.target.value } : item))} /></label>
          <div className="badge-row"><button className="button button--ghost button--sm" type="button" disabled={index === 0} onClick={() => setQuestions(questions.map((item, i) => i === index ? questions[index - 1]! : i === index - 1 ? questions[index]! : item))}>↑</button><button className="button button--ghost button--sm" type="button" disabled={index === questions.length - 1} onClick={() => setQuestions(questions.map((item, i) => i === index ? questions[index + 1]! : i === index + 1 ? questions[index]! : item))}>↓</button><button className="button button--ghost button--sm" type="button" disabled={questions.length === 1} onClick={() => setQuestions(questions.filter((_, i) => i !== index))}>Удалить вопрос</button></div>
        </fieldset>)}
        <div className="badge-row"><button className="button button--ghost" type="button" onClick={() => setQuestions([...questions, blankQuestion()])}>Добавить вопрос</button><button className="button button--primary" type="button" disabled={busy} onClick={() => void saveQuiz()}>{busy ? 'Сохранение…' : 'Сохранить тест'}</button></div>
        <div className="assessment-list">{quizzes.map((quiz) => <article className="assessment-list__row" key={quiz.id}><div><strong>{quiz.title}</strong><p className="muted">{quiz.status} · версия {quiz.version}{quiz.is_required ? ' · обязательно' : ''}</p></div><div className="badge-row"><button className="button button--ghost button--sm" onClick={() => editQuiz(quiz)}>Изменить</button>{quiz.status !== 'published' ? <button className="button button--primary button--sm" onClick={() => void setQuizStatus(token!, quiz.id, 'publish').then(reload).catch((e: unknown) => setError(String(e)))}>Опубликовать</button> : <button className="button button--ghost button--sm" onClick={() => void setQuizStatus(token!, quiz.id, 'unpublish').then(reload).catch((e: unknown) => setError(String(e)))}>Снять с публикации</button>}<button className="button button--ghost button--sm" onClick={() => void setQuizStatus(token!, quiz.id, 'archive').then(reload).catch((e: unknown) => setError(String(e)))}>Архивировать</button></div></article>)}</div>
      </section>

      <section className="card stack"><h2>{assignmentId ? 'Редактирование задания' : 'Создать практическое задание'}</h2><label className="field"><span>Название</span><input className="field__input" value={assignmentTitle} onChange={(event) => setAssignmentTitle(event.target.value)} /></label><label className="field"><span>Описание задачи</span><textarea className="field__input" value={assignmentDescription} onChange={(event) => setAssignmentDescription(event.target.value)} /></label><label className="field"><span>Требования к ответу</span><textarea className="field__input" value={requirements} onChange={(event) => setRequirements(event.target.value)} /></label><div className="assessment-form-grid"><label className="field"><span>Максимум баллов</span><input className="field__input" type="number" min="0.01" step="0.01" value={maxPoints} onChange={(event) => setMaxPoints(event.target.value)} /></label><label className="field"><span>Срок выполнения (необязательно)</span><input className="field__input" type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label></div><label className="assessment-option"><input type="checkbox" checked={assignmentRequired} onChange={(event) => setAssignmentRequired(event.target.checked)} />Обязательное для завершения курса</label><label className="assessment-option"><input type="checkbox" checked={allowResubmission} onChange={(event) => setAllowResubmission(event.target.checked)} />Разрешить повторную отправку</label><div className="badge-row"><button className="button button--primary" disabled={busy} onClick={() => void saveAssignment()}>{busy ? 'Сохранение…' : 'Сохранить задание'}</button>{assignmentId && <button className="button button--ghost" onClick={() => setAssignmentId(null)}>Отмена</button>}</div><div className="assessment-list">{assignments.map((assignment) => <article className="assessment-list__row" key={assignment.id}><div><strong>{assignment.title}</strong><p className="muted">{assignment.status} · {assignment.max_points} баллов</p></div><div className="badge-row"><button className="button button--ghost button--sm" onClick={() => { setAssignmentId(assignment.id); setAssignmentTitle(assignment.title); setAssignmentDescription(assignment.description); setRequirements(assignment.requirements ?? ''); setMaxPoints(String(assignment.max_points)); setAssignmentRequired(assignment.is_required); setDueAt(assignment.due_at?.slice(0, 16) ?? ''); setAllowResubmission(assignment.allow_resubmission); }}>Изменить</button><button className="button button--primary button--sm" onClick={() => void setAssignmentStatus(token!, assignment.id, assignment.status === 'published' ? 'unpublish' : 'publish').then(reload).catch((e: unknown) => setError(String(e)))}>{assignment.status === 'published' ? 'Снять' : 'Опубликовать'}</button><button className="button button--ghost button--sm" onClick={() => void setAssignmentStatus(token!, assignment.id, 'archive').then(reload).catch((e: unknown) => setError(String(e)))}>Архив</button></div></article>)}</div></section>

      <section className="card stack"><h2>Преподаватели курса</h2><p className="muted">Назначенный преподаватель видит и проверяет только работы этого курса.</p><div className="badge-row"><input className="field__input" placeholder="UUID пользователя с ролью teacher" value={instructorId} onChange={(event) => setInstructorId(event.target.value)} /><button className="button button--primary" onClick={() => token && void addInstructor(token, courseId, instructorId).then(reload).then(() => setInstructorId('')).catch((e: unknown) => setError(String(e)))}>Назначить</button></div>{instructors.map((item) => <div className="assessment-list__row" key={item.instructor_id}><span>{item.display_name} · {item.instructor_id}</span><button className="button button--ghost button--sm" onClick={() => token && void removeInstructor(token, courseId, item.instructor_id).then(reload).catch((e: unknown) => setError(String(e)))}>Снять</button></div>)}</section>
    </main>
  );
}
