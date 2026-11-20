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
          <p className="app__kicker">Sprint 4 · Процесс обучения</p>
          <h1 className="app__title">Education Platform</h1>
          <p className="app__subtitle">
            Каталог публичных курсов, кабинет автора и полноценное обучение: запись на курс,
            три состояния урока, прогресс и журнал. Материалы урока открываются только тем,
            кто записан на опубликованный курс.
          </p>
          <div className="app__actions">
            <Link className="button button--primary" to="/catalog">
              Открыть каталог
            </Link>
            {status === 'authenticated' ? (
              <>
                <Link className="button button--ghost" to="/my-learning">
                  Моё обучение
                </Link>
                <Link className="button button--ghost" to="/profile">
                  Перейти в профиль
                </Link>
              </>
            ) : (
              <>
                <Link className="button button--ghost" to="/register">
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
