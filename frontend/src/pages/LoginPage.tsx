import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { describeAuthError } from '../utils/authErrors';
import { validateEmail } from '../utils/validation';
import './auth.css';

interface FieldErrors {
  email?: string;
  password?: string;
}

interface LocationState {
  from?: string;
}

export function LoginPage() {
  const { status, signInWithPassword } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as LocationState | null)?.from ?? '/profile';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authenticated') {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    const errors: FieldErrors = {};
    const emailError = validateEmail(email);
    if (emailError !== null) {
      errors.email = emailError;
    }
    if (password.length === 0) {
      errors.password = 'Укажите пароль.';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      await signInWithPassword(email.trim(), password);
      navigate(from, { replace: true });
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
          <p className="eyebrow">Аккаунт</p>
          <h1 className="auth-card__title">Вход</h1>
          <p className="muted">Войдите, чтобы открыть личный профиль.</p>
        </header>

        {formError !== null && (
          <p className="alert alert--error" role="alert">
            {formError}
          </p>
        )}

        <form className="form" onSubmit={handleSubmit} noValidate>
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
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={fieldErrors.password !== undefined}
              disabled={submitting}
            />
            {fieldErrors.password !== undefined && (
              <span className="field__error">{fieldErrors.password}</span>
            )}
          </label>

          <button
            type="submit"
            className="button button--primary button--block"
            disabled={submitting}
          >
            {submitting ? 'Вход…' : 'Войти'}
          </button>
        </form>

        <p className="auth-card__footer">
          Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
        </p>
      </section>
    </main>
  );
}
