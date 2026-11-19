import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { describeAuthError } from '../utils/authErrors';
import {
  PASSWORD_MIN_LENGTH,
  validateDisplayName,
  validateEmail,
  validatePassword,
} from '../utils/validation';
import './auth.css';

interface FieldErrors {
  email?: string;
  password?: string;
  displayName?: string;
}

export function RegisterPage() {
  const { status, signUp } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authenticated') {
    return <Navigate to="/profile" replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    const errors: FieldErrors = {};
    const nameError = validateDisplayName(displayName);
    if (nameError !== null) {
      errors.displayName = nameError;
    }
    const emailError = validateEmail(email);
    if (emailError !== null) {
      errors.email = emailError;
    }
    const passwordError = validatePassword(password);
    if (passwordError !== null) {
      errors.password = passwordError;
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      await signUp({
        display_name: displayName.trim(),
        email: email.trim(),
        password,
      });
      navigate('/profile', { replace: true });
    } catch (error) {
      setFormError(describeAuthError(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="page">
      <section className="card auth-card">
        <header className="auth-card__header">
          <p className="eyebrow">Новый аккаунт</p>
          <h1 className="auth-card__title">Регистрация</h1>
          <p className="muted">
            После регистрации вы сразу войдёте в систему и получите базовую роль
            «Пользователь».
          </p>
        </header>

        {formError !== null && (
          <p className="alert alert--error" role="alert">
            {formError}
          </p>
        )}

        <form className="form" onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span className="field__label">Имя</span>
            <input
              className="input"
              type="text"
              name="display_name"
              autoComplete="name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              aria-invalid={fieldErrors.displayName !== undefined}
              disabled={submitting}
              placeholder="Как к вам обращаться"
            />
            {fieldErrors.displayName !== undefined && (
              <span className="field__error">{fieldErrors.displayName}</span>
            )}
          </label>

          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="input"
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={fieldErrors.email !== undefined}
              disabled={submitting}
              placeholder="you@example.com"
            />
            {fieldErrors.email !== undefined && (
              <span className="field__error">{fieldErrors.email}</span>
            )}
          </label>

          <label className="field">
            <span className="field__label">Пароль</span>
            <input
              className="input"
              type="password"
              name="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={fieldErrors.password !== undefined}
              disabled={submitting}
            />
            <span className="field__hint">
              Не менее {PASSWORD_MIN_LENGTH} символов, минимум одна буква и одна цифра.
            </span>
            {fieldErrors.password !== undefined && (
              <span className="field__error">{fieldErrors.password}</span>
            )}
          </label>

          <button
            type="submit"
            className="button button--primary button--block"
            disabled={submitting}
          >
            {submitting ? 'Создание аккаунта…' : 'Создать аккаунт'}
          </button>
        </form>

        <p className="auth-card__footer">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </section>
    </main>
  );
}
