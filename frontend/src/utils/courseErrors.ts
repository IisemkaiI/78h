/** Russian messages for course-specific API errors. */

import { ApiError } from '../services/apiClient';

const MESSAGES: Record<string, string> = {
  course_not_found: 'Курс не найден или недоступен.',
  module_not_found: 'Модуль не найден.',
  lesson_not_found: 'Урок не найден.',
  category_not_found: 'Категория не найдена.',
  category_inactive: 'Выбранная категория отключена.',
  invalid_order: 'Некорректный порядок элементов. Обновите страницу и попробуйте снова.',
  course_not_ready: 'Курс пока нельзя опубликовать: заполните недостающие данные.',
  course_has_enrollments:
    'У курса есть записи обучающихся, поэтому его нельзя удалить. Переведите курс в архив.',
};

const MISSING_LABELS: Record<string, string> = {
  title: 'название курса',
  short_description: 'краткое описание',
  description: 'полное описание',
  active_category: 'активная категория',
  level: 'уровень сложности',
  language: 'язык курса',
  modules: 'хотя бы один модуль',
};

/** Turn a `course_not_ready` payload into a readable checklist. */
function missingFieldLabel(field: string): string {
  const plain = MISSING_LABELS[field];
  if (plain !== undefined) {
    return plain;
  }

  const lesson = /^module_(\d+)_lesson_(\d+)_(title|duration)$/.exec(field);
  if (lesson !== null) {
    const moduleIndex = lesson[1] ?? '?';
    const lessonIndex = lesson[2] ?? '?';
    const kind = lesson[3];
    return kind === 'title'
      ? `название урока ${lessonIndex} в модуле ${moduleIndex}`
      : `длительность урока ${lessonIndex} в модуле ${moduleIndex}`;
  }

  const moduleMatch = /^module_(\d+)_(title|lessons)$/.exec(field);
  if (moduleMatch !== null) {
    const moduleIndex = moduleMatch[1] ?? '?';
    const kind = moduleMatch[2];
    return kind === 'title'
      ? `название модуля ${moduleIndex}`
      : `уроки в модуле ${moduleIndex}`;
  }

  return field;
}

export function describeCourseError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'course_not_ready') {
      const details = error.details;
      if (
        typeof details === 'object' &&
        details !== null &&
        'missing' in details &&
        Array.isArray((details as { missing: unknown }).missing)
      ) {
        const missing = (details as { missing: unknown[] }).missing
          .filter((item): item is string => typeof item === 'string')
          .map(missingFieldLabel);
        if (missing.length > 0) {
          return `Курс пока нельзя опубликовать. Не хватает: ${missing.join(', ')}.`;
        }
      }
      return MESSAGES.course_not_ready ?? 'Курс пока нельзя опубликовать: заполните недостающие данные.';
    }
    return MESSAGES[error.code] ?? error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Неизвестная ошибка. Попробуйте ещё раз.';
}

/** The `details.missing` list of a publish failure, if present. */
export function publishMissingFields(error: unknown): string[] {
  if (!(error instanceof ApiError) || error.code !== 'course_not_ready') {
    return [];
  }
  const details = error.details;
  if (
    typeof details === 'object' &&
    details !== null &&
    'missing' in details &&
    Array.isArray((details as { missing: unknown }).missing)
  ) {
    return (details as { missing: unknown[] }).missing
      .filter((item): item is string => typeof item === 'string')
      .map(missingFieldLabel);
  }
  return [];
}
