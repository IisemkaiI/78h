import { Link } from 'react-router-dom';

import logoUrl from '../assets/logo.svg';
import { ConnectionStatus } from '../components/ConnectionStatus/ConnectionStatus';
import { useAuth } from '../auth/AuthContext';
import { useBackendStatus } from '../hooks/useBackendStatus';

export function HomePage() {
  const { state, refresh } = useBackendStatus();
  const { status } = useAuth();

  return (
    <main className="app">
      <div className="app__inner">
        <header className="app__header">
          <img className="app__logo" src={logoUrl} alt="" width={48} height={48} />
          <p className="app__kicker">Sprint 1 · Пользователи и доступ</p>
          <h1 className="app__title">Education Platform</h1>
          <p className="app__subtitle">
            Базовая система пользователей платформы: регистрация, вход по email и паролю,
            личный профиль и ролевая модель доступа. Остальные модули появятся в следующих
            спринтах.
          </p>
          <div className="app__actions">
            {status === 'authenticated' ? (
              <Link className="button button--primary" to="/profile">
                Перейти в профиль
              </Link>
            ) : (
              <>
                <Link className="button button--primary" to="/register">
                  Создать аккаунт
                </Link>
                <Link className="button button--ghost" to="/login">
                  Войти
                </Link>
              </>
            )}
          </div>
        </header>

        <ConnectionStatus {...state} onRefresh={refresh} />

        <footer className="app__footer">
          <span>Frontend: React + TypeScript + Vite</span>
          <span>Backend: FastAPI + SQLAlchemy 2</span>
          <span>Database: PostgreSQL (Docker Compose)</span>
        </footer>
      </div>
    </main>
  );
}
