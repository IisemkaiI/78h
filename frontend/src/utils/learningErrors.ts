/** Russian messages for learning-specific API errors. */

import { ApiError } from '../services/apiClient';

const MESSAGES: Record<string, string> = {
  course_not_found: 'Курс не найден или больше не опубликован.',
  course_not_completed: 'Завершите все уроки и обязательные проверки, чтобы получить сертификат.',
  course_not_available: 'Курс временно закрыт для обучения. Запись сохранена.',
  enrollment_required: 'Для доступа к материалам нужна активная запись на курс.',
  enrollment_not_found: 'Запись на курс не найдена.',
  enrollment_cancelled: 'Запись на этот курс уже отменена.',
  already_enrolled: 'Вы уже записаны на этот курс.',
  own_course_enrollment_forbidden: 'Автор не может записаться на собственный курс.',
  lesson_not_found: 'Урок не найден в программе курса.',
  course_has_enrollments:
    'У курса есть записи обучающихся, поэтому его нельзя удалить. Переведите курс в архив.',
};

export function describeLearningError(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code] ?? error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Неизвестная ошибка. Попробуйте ещё раз.';
}
