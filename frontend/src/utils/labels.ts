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
