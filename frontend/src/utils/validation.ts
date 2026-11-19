const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const PASSWORD_MIN_LENGTH = 10;

export function validateEmail(value: string): string | null {
  const email = value.trim();
  if (email.length === 0) {
    return 'Укажите email.';
  }
  if (!EMAIL_PATTERN.test(email)) {
    return 'Введите корректный email.';
  }
  return null;
}

export function validatePassword(value: string): string | null {
  if (value.length === 0) {
    return 'Укажите пароль.';
  }
  if (value.length < PASSWORD_MIN_LENGTH) {
    return `Пароль должен содержать не менее ${PASSWORD_MIN_LENGTH} символов.`;
  }
  if (value.length > 128) {
    return 'Пароль слишком длинный (максимум 128 символов).';
  }
  if (value !== value.trim()) {
    return 'Пароль не должен начинаться или заканчиваться пробелом.';
  }
  if (!/[A-Za-zА-Яа-яЁё]/.test(value)) {
    return 'Пароль должен содержать хотя бы одну букву.';
  }
  if (!/\d/.test(value)) {
    return 'Пароль должен содержать хотя бы одну цифру.';
  }
  return null;
}

export function validateDisplayName(value: string): string | null {
  const name = value.trim();
  if (name.length < 2) {
    return 'Имя должно содержать не менее 2 символов.';
  }
  if (name.length > 120) {
    return 'Имя слишком длинное (максимум 120 символов).';
  }
  return null;
}
