import { ApiError } from '../services/apiClient';

const MESSAGES: Record<string, string> = {
  invalid_credentials: 'Неверный email или пароль.',
  account_inactive: 'Аккаунт деактивирован. Обратитесь к администратору.',
  email_already_registered: 'Аккаунт с таким email уже существует.',
  weak_password: 'Пароль не соответствует требованиям безопасности.',
  validation_error: 'Проверьте правильность заполнения полей.',
  not_authenticated: 'Требуется авторизация.',
  invalid_token: 'Сессия недействительна. Войдите снова.',
  token_expired: 'Сессия истекла. Войдите снова.',
  insufficient_permissions: 'Недостаточно прав для этого действия.',
  insufficient_roles: 'Недостаточно прав для этого действия.',
};

/** Human-readable Russian message for an API or network failure. */
export function describeAuthError(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code] ?? error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Неизвестная ошибка. Попробуйте ещё раз.';
}
