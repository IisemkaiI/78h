import { useState, type FormEvent } from 'react';

import {
  createModule,
  reorderModules,
} from '../../services/courseService';
import type { CourseDetail, CourseModule, Lesson } from '../../types/api';
import { describeCourseError } from '../../utils/courseErrors';
import { ModuleEditor } from './ModuleEditor';

function recalculate(course: CourseDetail, modules: CourseModule[]): CourseDetail {
  const lessonsCount = modules.reduce((sum, module) => sum + module.lessons.length, 0);
  const totalDuration = modules.reduce(
    (sum, module) =>
      sum +
      module.lessons.reduce(
        (inner, lesson) => inner + lesson.estimated_duration_minutes,
        0,
      ),
    0,
  );
  return {
    ...course,
    modules,
    modules_count: modules.length,
    lessons_count: lessonsCount,
    total_duration_minutes: totalDuration,
  };
}

export function CourseStructure({
  token,
  course,
  onChange,
  onError,
}: {
  token: string;
  course: CourseDetail;
  onChange: (course: CourseDetail) => void;
  onError: (message: string | null) => void;
}) {
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleAddModule = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setBusy(true);
    onError(null);
    try {
      const module = await createModule(token, course.id, {
        title: newTitle.trim(),
        description: newDescription.trim() || null,
      });
      onChange(recalculate(course, [...course.modules, module]));
      setNewTitle('');
      setNewDescription('');
      setAdding(false);
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  const handleModuleUpdated = (updated: CourseModule): void => {
    onChange(
      recalculate(
        course,
        course.modules.map((module) => (module.id === updated.id ? updated : module)),
      ),
    );
  };

  const handleModuleDeleted = (moduleId: string): void => {
    onChange(
      recalculate(
        course,
        course.modules
          .filter((module) => module.id !== moduleId)
          .map((module, index) => ({ ...module, position: index + 1 })),
      ),
    );
  };

  const handleModuleMove = async (moduleId: string, direction: -1 | 1): Promise<void> => {
    const index = course.modules.findIndex((module) => module.id === moduleId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= course.modules.length) {
      return;
    }
    const next = [...course.modules];
    const current = next[index]!;
    next[index] = next[target]!;
    next[target] = current;
    setBusy(true);
    onError(null);
    try {
      const reordered = await reorderModules(
        token,
        course.id,
        next.map((module) => module.id),
      );
      onChange(recalculate(course, reordered));
    } catch (caught) {
      onError(describeCourseError(caught));
    } finally {
      setBusy(false);
    }
  };

  const handleLessonsChange = (moduleId: string, lessons: Lesson[]): void => {
    onChange(
      recalculate(
        course,
        course.modules.map((module) =>
          module.id === moduleId ? { ...module, lessons } : module,
        ),
      ),
    );
  };

  return (
    <section className="card stack structure" aria-labelledby="structure-title">
      <div className="structure__header">
        <div>
          <h2 id="structure-title">Структура курса</h2>
          <p className="muted">
            Модули и уроки упорядочены сверху вниз. Для публикации нужен хотя бы один модуль
            с хотя бы одним уроком.
          </p>
        </div>
        <span className="badge">
          {course.modules_count} модулей · {course.lessons_count} уроков
        </span>
      </div>

      {course.modules.length === 0 ? (
        <p className="muted">Модулей пока нет. Добавьте первый модуль.</p>
      ) : (
        <ol className="module-list">
          {course.modules.map((module, index) => (
            <ModuleEditor
              key={module.id}
              token={token}
              courseId={course.id}
              module={module}
              isFirst={index === 0}
              isLast={index === course.modules.length - 1}
              onUpdated={handleModuleUpdated}
              onDeleted={handleModuleDeleted}
              onMove={(moduleId, direction) => void handleModuleMove(moduleId, direction)}
              onLessonsChange={handleLessonsChange}
              onError={onError}
            />
          ))}
        </ol>
      )}

      {adding ? (
        <form className="card stack structure__add-form" onSubmit={handleAddModule}>
          <h3>Новый модуль</h3>
          <label className="field">
            <span className="field__label">Название модуля *</span>
            <input
              className="input"
              value={newTitle}
              onChange={(event) => setNewTitle(event.target.value)}
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
              value={newDescription}
              onChange={(event) => setNewDescription(event.target.value)}
              maxLength={2000}
              disabled={busy}
            />
          </label>
          <div className="editor-actions">
            <button type="submit" className="button button--primary button--sm" disabled={busy}>
              {busy ? 'Добавление…' : 'Добавить модуль'}
            </button>
            <button
              type="button"
              className="button button--ghost button--sm"
              disabled={busy}
              onClick={() => setAdding(false)}
            >
              Отмена
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          className="button button--ghost"
          onClick={() => setAdding(true)}
          disabled={busy}
        >
          + Добавить модуль
        </button>
      )}
    </section>
  );
}
