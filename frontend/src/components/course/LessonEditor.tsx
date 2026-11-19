import { useState, type FormEvent } from 'react';

import { deleteLesson, updateLesson } from '../../services/courseService';
import type { Lesson } from '../../types/api';
import { describeCourseError } from '../../utils/courseErrors';
import { formatDuration } from '../../utils/labels';

export function LessonEditor({
  token,
  courseId,
  moduleId,
  lesson,
  isFirst,
  isLast,
  onUpdated,
  onDeleted,
  onMove,
  onError,
}: {
  token: string;
  courseId: string;
  moduleId: string;
  lesson: Lesson;
  isFirst: boolean;
  isLast: boolean;
  onUpdated: (lesson: Lesson) => void;
  onDeleted: (lessonId: string) => void;
  onMove: (lessonId: string, direction: -1 | 1) => void;
  onError: (message: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(lesson.title);
  const [description, setDescription] = useState(lesson.description ?? '');
  const [content, setContent] = useState(lesson.content);
  const [duration, setDuration] = useState(String(lesson.estimated_duration_minutes));
  const [busy, setBusy] = useState(false);

  const resetForm = (): void => {
    setTitle(lesson.title);
    setDescription(lesson.description ?? '');
    setContent(lesson.content);
    setDuration(String(lesson.estimated_duration_minutes));
  };

  const handleSave = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setBusy(true);
    onError(null);
    try {
      const updated = await updateLesson(token, courseId, moduleId, lesson.id, {
        title: title.trim(),
        description: description.trim() || null,
        content,
        estimated_duration_minutes: Number(duration) || 0,
      });
      onUpdated(updated);
      setEditing(false);
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!window.confirm(`Удалить урок «${lesson.title}»?`)) {
      return;
    }
    setBusy(true);
    onError(null);
    try {
      await deleteLesson(token, courseId, moduleId, lesson.id);
      onDeleted(lesson.id);
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="lesson-editor">
      {editing ? (
        <form className="lesson-editor__form" onSubmit={handleSave}>
          <label className="field">
            <span className="field__label">Название урока *</span>
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
            <span className="field__label">Краткое описание</span>
            <textarea
              className="input textarea"
              rows={2}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={2000}
              disabled={busy}
            />
          </label>

          <label className="field">
            <span className="field__label">Содержимое (Markdown)</span>
            <textarea
              className="input textarea textarea--code"
              rows={8}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              disabled={busy}
            />
            <span className="field__hint">
              Поддерживается Markdown: заголовки, списки, код. Загрузка файлов и видео
              появится позже.
            </span>
          </label>

          <label className="field lesson-editor__duration">
            <span className="field__label">Длительность, минут</span>
            <input
              className="input"
              type="number"
              min={0}
              max={10000}
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
              disabled={busy}
            />
          </label>

          <div className="editor-actions">
            <button type="submit" className="button button--primary button--sm" disabled={busy}>
              {busy ? 'Сохранение…' : 'Сохранить урок'}
            </button>
            <button
              type="button"
              className="button button--ghost button--sm"
              disabled={busy}
              onClick={() => {
                resetForm();
                setEditing(false);
              }}
            >
              Отмена
            </button>
          </div>
        </form>
      ) : (
        <div className="lesson-editor__summary">
          <div className="lesson-editor__info">
            <span className="lesson-editor__position">{lesson.position}</span>
            <div>
              <p className="lesson-editor__title">{lesson.title}</p>
              {lesson.description !== null && (
                <p className="muted lesson-editor__description">{lesson.description}</p>
              )}
            </div>
          </div>

          <div className="lesson-editor__actions">
            <span className="badge">{formatDuration(lesson.estimated_duration_minutes)}</span>
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={() => onMove(lesson.id, -1)}
              disabled={isFirst || busy}
              title="Выше"
              aria-label="Переместить урок выше"
            >
              ↑
            </button>
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={() => onMove(lesson.id, 1)}
              disabled={isLast || busy}
              title="Ниже"
              aria-label="Переместить урок ниже"
            >
              ↓
            </button>
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={() => {
                resetForm();
                setEditing(true);
              }}
              disabled={busy}
            >
              Изменить
            </button>
            <button
              type="button"
              className="button button--danger button--sm"
              onClick={() => void handleDelete()}
              disabled={busy}
            >
              Удалить
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
