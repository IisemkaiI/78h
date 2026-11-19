import { useState, type FormEvent } from 'react';

import {
  createLesson,
  deleteModule,
  reorderLessons,
  updateModule,
} from '../../services/courseService';
import type { CourseModule, Lesson } from '../../types/api';
import { describeCourseError } from '../../utils/courseErrors';
import { formatDuration } from '../../utils/labels';
import { LessonEditor } from './LessonEditor';

export function ModuleEditor({
  token,
  courseId,
  module,
  isFirst,
  isLast,
  onUpdated,
  onDeleted,
  onMove,
  onLessonsChange,
  onError,
}: {
  token: string;
  courseId: string;
  module: CourseModule;
  isFirst: boolean;
  isLast: boolean;
  onUpdated: (module: CourseModule) => void;
  onDeleted: (moduleId: string) => void;
  onMove: (moduleId: string, direction: -1 | 1) => void;
  onLessonsChange: (moduleId: string, lessons: Lesson[]) => void;
  onError: (message: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(module.title);
  const [description, setDescription] = useState(module.description ?? '');
  const [addingLesson, setAddingLesson] = useState(false);
  const [newLessonTitle, setNewLessonTitle] = useState('');
  const [newLessonDescription, setNewLessonDescription] = useState('');
  const [newLessonContent, setNewLessonContent] = useState('');
  const [newLessonDuration, setNewLessonDuration] = useState('15');
  const [busy, setBusy] = useState(false);

  const totalMinutes = module.lessons.reduce(
    (sum, lesson) => sum + lesson.estimated_duration_minutes,
    0,
  );

  const handleSaveModule = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setBusy(true);
    onError(null);
    try {
      const updated = await updateModule(token, courseId, module.id, {
        title: title.trim(),
        description: description.trim() || null,
      });
      onUpdated(updated);
      setEditing(false);
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteModule = async (): Promise<void> => {
    if (
      !window.confirm(
        `Удалить модуль «${module.title}» вместе с ${module.lessons.length} уроками?`,
      )
    ) {
      return;
    }
    setBusy(true);
    onError(null);
    try {
      await deleteModule(token, courseId, module.id);
      onDeleted(module.id);
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  const handleAddLesson = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setBusy(true);
    onError(null);
    try {
      const lesson = await createLesson(token, courseId, module.id, {
        title: newLessonTitle.trim(),
        description: newLessonDescription.trim() || null,
        content: newLessonContent,
        estimated_duration_minutes: Number(newLessonDuration) || 0,
      });
      onLessonsChange(module.id, [...module.lessons, lesson]);
      setNewLessonTitle('');
      setNewLessonDescription('');
      setNewLessonContent('');
      setNewLessonDuration('15');
      setAddingLesson(false);
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  const handleLessonUpdated = (lesson: Lesson): void => {
    onLessonsChange(
      module.id,
      module.lessons.map((item) => (item.id === lesson.id ? lesson : item)),
    );
  };

  const handleLessonDeleted = (lessonId: string): void => {
    onLessonsChange(
      module.id,
      module.lessons
        .filter((item) => item.id !== lessonId)
        .map((item, index) => ({ ...item, position: index + 1 })),
    );
  };

  const handleLessonMove = async (lessonId: string, direction: -1 | 1): Promise<void> => {
    const index = module.lessons.findIndex((item) => item.id === lessonId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= module.lessons.length) {
      return;
    }
    const next = [...module.lessons];
    const current = next[index]!;
    next[index] = next[target]!;
    next[target] = current;
    setBusy(true);
    onError(null);
    try {
      const reordered = await reorderLessons(
        token,
        courseId,
        module.id,
        next.map((item) => item.id),
      );
      onLessonsChange(module.id, reordered);
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="module-editor card">
      <div className="module-editor__header">
        <div className="module-editor__heading">
          <span className="module-editor__position">{module.position}</span>
          <div>
            <h3 className="module-editor__title">{module.title}</h3>
            <p className="muted module-editor__meta">
              {module.lessons.length} уроков · {formatDuration(totalMinutes)}
            </p>
          </div>
        </div>

        <div className="module-editor__actions">
          <button
            type="button"
            className="button button--ghost button--sm"
            onClick={() => onMove(module.id, -1)}
            disabled={isFirst || busy}
            aria-label="Переместить модуль выше"
            title="Выше"
          >
            ↑
          </button>
          <button
            type="button"
            className="button button--ghost button--sm"
            onClick={() => onMove(module.id, 1)}
            disabled={isLast || busy}
            aria-label="Переместить модуль ниже"
            title="Ниже"
          >
            ↓
          </button>
          <button
            type="button"
            className="button button--ghost button--sm"
            onClick={() => {
              setTitle(module.title);
              setDescription(module.description ?? '');
              setEditing((value) => !value);
            }}
            disabled={busy}
          >
            {editing ? 'Отмена' : 'Изменить'}
          </button>
          <button
            type="button"
            className="button button--danger button--sm"
            onClick={() => void handleDeleteModule()}
            disabled={busy}
          >
            Удалить
          </button>
        </div>
      </div>

      {editing ? (
        <form className="module-editor__form" onSubmit={handleSaveModule}>
          <label className="field">
            <span className="field__label">Название модуля *</span>
            <input
              className="input"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={200}
              disabled={busy}
              required
            />
          </label>
          <label className="field">
            <span className="field__label">Описание</span>
            <textarea
              className="input textarea"
              rows={2}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={2000}
              disabled={busy}
            />
          </label>
          <div className="editor-actions">
            <button type="submit" className="button button--primary button--sm" disabled={busy}>
              {busy ? 'Сохранение…' : 'Сохранить модуль'}
            </button>
          </div>
        </form>
      ) : (
        module.description !== null && (
          <p className="muted module-editor__description">{module.description}</p>
        )
      )}

      {module.lessons.length === 0 ? (
        <p className="muted module-editor__empty">
          В модуле пока нет уроков. Добавьте хотя бы один — без уроков курс нельзя
          опубликовать.
        </p>
      ) : (
        <ol className="lesson-list">
          {module.lessons.map((lesson, index) => (
            <LessonEditor
              key={lesson.id}
              token={token}
              courseId={courseId}
              moduleId={module.id}
              lesson={lesson}
              isFirst={index === 0}
              isLast={index === module.lessons.length - 1}
              onUpdated={handleLessonUpdated}
              onDeleted={handleLessonDeleted}
              onMove={(lessonId, direction) => void handleLessonMove(lessonId, direction)}
              onError={onError}
            />
          ))}
        </ol>
      )}

      {addingLesson ? (
        <form className="module-editor__add-form card" onSubmit={handleAddLesson}>
          <h4>Новый урок</h4>
          <label className="field">
            <span className="field__label">Название урока *</span>
            <input
              className="input"
              value={newLessonTitle}
              onChange={(event) => setNewLessonTitle(event.target.value)}
              maxLength={200}
              disabled={busy}
              required
            />
          </label>
          <label className="field">
            <span className="field__label">Краткое описание</span>
            <textarea
              className="input textarea"
              rows={2}
              value={newLessonDescription}
              onChange={(event) => setNewLessonDescription(event.target.value)}
              maxLength={2000}
              disabled={busy}
            />
          </label>
          <label className="field">
            <span className="field__label">Содержимое (Markdown)</span>
            <textarea
              className="input textarea textarea--code"
              rows={5}
              value={newLessonContent}
              onChange={(event) => setNewLessonContent(event.target.value)}
              disabled={busy}
            />
          </label>
          <label className="field module-editor__duration">
            <span className="field__label">Длительность, минут</span>
            <input
              className="input"
              type="number"
              min={0}
              max={10000}
              value={newLessonDuration}
              onChange={(event) => setNewLessonDuration(event.target.value)}
              disabled={busy}
            />
          </label>
          <div className="editor-actions">
            <button type="submit" className="button button--primary button--sm" disabled={busy}>
              {busy ? 'Добавление…' : 'Добавить урок'}
            </button>
            <button
              type="button"
              className="button button--ghost button--sm"
              disabled={busy}
              onClick={() => setAddingLesson(false)}
            >
              Отмена
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => setAddingLesson(true)}
          disabled={busy}
        >
          + Добавить урок
        </button>
      )}
    </li>
  );
}
