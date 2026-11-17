import type { BackendStatus, HealthResponse, InfoResponse, ReadyResponse } from '../../types/api';
import { API_BASE_URL } from '../../services/apiClient';
import './ConnectionStatus.css';

interface StatusAppearance {
  label: string;
  tone: 'checking' | 'success' | 'danger';
}

const APPEARANCE: Record<BackendStatus, StatusAppearance> = {
  checking: { label: 'Проверка соединения выполняется…', tone: 'checking' },
  online: { label: 'Backend доступен', tone: 'success' },
  offline: { label: 'Backend недоступен', tone: 'danger' },
};

export interface ConnectionStatusProps {
  status: BackendStatus;
  health: HealthResponse | null;
  info: InfoResponse | null;
  ready: ReadyResponse | null;
  error: string | null;
  latencyMs: number | null;
  checkedAt: Date | null;
  onRefresh: () => void;
}

function databaseRow(ready: ReadyResponse | null, status: BackendStatus): {
  label: string;
  tone: 'success' | 'danger' | 'muted';
} {
  if (status === 'checking') {
    return { label: 'Проверка…', tone: 'muted' };
  }
  if (status === 'offline' || ready === null) {
    return { label: 'Неизвестно', tone: 'muted' };
  }
  if (ready.database.status === 'available') {
    return {
      label:
        ready.database.latency_ms === null
          ? 'PostgreSQL доступна'
          : `PostgreSQL доступна (${ready.database.latency_ms} мс)`,
      tone: 'success',
    };
  }
  return { label: 'PostgreSQL недоступна', tone: 'danger' };
}

export function ConnectionStatus({
  status,
  health,
  info,
  ready,
  error,
  latencyMs,
  checkedAt,
  onRefresh,
}: ConnectionStatusProps) {
  const appearance = APPEARANCE[status];
  const database = databaseRow(ready, status);

  return (
    <section className="connection" aria-live="polite" aria-busy={status === 'checking'}>
      <header className="connection__header">
        <span className={`connection__badge connection__badge--${appearance.tone}`}>
          <span className="connection__dot" aria-hidden="true" />
          {appearance.label}
        </span>
        <button
          type="button"
          className="connection__refresh"
          onClick={onRefresh}
          disabled={status === 'checking'}
        >
          Проверить снова
        </button>
      </header>

      <dl className="connection__details">
        <div className="connection__row">
          <dt>API</dt>
          <dd>
            <code>{API_BASE_URL}</code>
          </dd>
        </div>
        <div className="connection__row">
          <dt>Версия backend</dt>
          <dd>{health?.version ?? '—'}</dd>
        </div>
        <div className="connection__row">
          <dt>Окружение</dt>
          <dd>{info?.environment ?? health?.environment ?? '—'}</dd>
        </div>
        <div className="connection__row">
          <dt>База данных</dt>
          <dd className={`connection__value connection__value--${database.tone}`}>
            {database.label}
          </dd>
        </div>
        <div className="connection__row">
          <dt>Время ответа</dt>
          <dd>{latencyMs === null ? '—' : `${latencyMs} мс`}</dd>
        </div>
        <div className="connection__row">
          <dt>Последняя проверка</dt>
          <dd>{checkedAt === null ? '—' : checkedAt.toLocaleTimeString('ru-RU')}</dd>
        </div>
      </dl>

      {error !== null && (
        <p className="connection__error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
