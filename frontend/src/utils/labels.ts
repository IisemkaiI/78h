const ROLE_LABELS: Record<string, string> = {
  guest: 'Гость',
  user: 'Пользователь',
  course_author: 'Автор курсов',
  teacher: 'Преподаватель',
  organization_employee: 'Сотрудник организации',
  organization_manager: 'Руководитель организации',
  admin: 'Администратор',
};

export function roleLabel(code: string): string {
  return ROLE_LABELS[code] ?? code;
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

const COURSE_LEVEL_LABELS: Record<string, string> = {
  beginner: 'Начальный',
  intermediate: 'Средний',
  advanced: 'Продвинутый',
};

const COURSE_STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  published: 'Опубликован',
  archived: 'В архиве',
};

export function courseLevelLabel(level: string): string {
  return COURSE_LEVEL_LABELS[level] ?? level;
}

export function courseStatusLabel(status: string): string {
  return COURSE_STATUS_LABELS[status] ?? status;
}

/** "45 мин", "2 ч 15 мин", "—" for unknown durations. */
export function formatDuration(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return '—';
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) {
    return `${rest} мин`;
  }
  return rest === 0 ? `${hours} ч` : `${hours} ч ${rest} мин`;
}
