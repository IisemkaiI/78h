import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { ApiError } from '../services/apiClient';
import { acceptOrganizationInvitation } from '../services/organizationService';
import { useAuth } from '../auth/AuthContext';

function invitationError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Войдите в аккаунт, чтобы принять приглашение.';
    if (error.status === 403) return 'Приглашение выдано для другого email-адреса.';
    if (error.status === 404) return 'Токен приглашения неверен или не существует.';
    if (error.status === 409) return error.message;
    if (error.status === 410) return 'Срок действия приглашения истёк.';
    return error.message;
  }
  return 'Не удалось принять приглашение. Проверьте соединение и повторите попытку.';
}

export function AcceptOrganizationInvitationPage() {
  const { token, status } = useAuth();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [invitationToken, setInvitationToken] = useState(searchParams.get('token') ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (!token || !invitationToken.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await acceptOrganizationInvitation(token, invitationToken.trim());
      navigate(`/organizations/${result.organization_id}`, { replace: true });
    } catch (caught) {
      setError(invitationError(caught));
    } finally {
      setSubmitting(false);
    }
  };

  if (status === 'loading') return <main className="page page--centered"><p role="status" className="page__status">Проверяем сессию…</p></main>;

  return (
    <main className="page organization-page organization-accept-page">
      <Link to="/organizations" className="text-link">← К организациям</Link>
      <section className="card organization-accept-card">
        <p className="eyebrow">Приглашение в команду</p>
        <h1 className="page__title">Присоединиться к организации</h1>
        <p className="muted">Войдите в аккаунт, для которого создано приглашение, и вставьте полученный одноразовый токен.</p>
        {status === 'anonymous' ? <div className="organization-login-prompt"><Link className="button button--primary" to="/login" state={{ from: `${location.pathname}${location.search}` }}>Войти в аккаунт</Link><p className="field__hint">После входа вернитесь на эту страницу, чтобы принять приглашение.</p></div> : (
          <form className="form" onSubmit={(event) => void submit(event)}>
            <label className="field"><span className="field__label">Одноразовый токен</span><textarea className="input organization-token-input" rows={4} required minLength={32} maxLength={128} value={invitationToken} onChange={(event) => setInvitationToken(event.target.value)} disabled={submitting} placeholder="Вставьте токен приглашения" /></label>
            {error && <p className="alert alert--error" role="alert">{error}</p>}
            <button className="button button--primary" disabled={submitting || invitationToken.trim().length < 32}>{submitting ? 'Принимаем приглашение…' : 'Принять приглашение'}</button>
          </form>
        )}
      </section>
    </main>
  );
}
