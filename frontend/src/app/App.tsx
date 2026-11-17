import logoUrl from '../assets/logo.svg';
import { ConnectionStatus } from '../components/ConnectionStatus/ConnectionStatus';
import { useBackendStatus } from '../hooks/useBackendStatus';
import './App.css';

export function App() {
  const { state, refresh } = useBackendStatus();

  return (
    <main className="app">
      <div className="app__inner">
        <header className="app__header">
          <img className="app__logo" src={logoUrl} alt="" width={48} height={48} />
          <p className="app__kicker">Sprint 0 · Project Foundation</p>
          <h1 className="app__title">Education Platform</h1>
          <p className="app__subtitle">
            Технический фундамент платформы: React-клиент, FastAPI и подключение к PostgreSQL.
            Функциональные модули появятся в следующих спринтах.
          </p>
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
