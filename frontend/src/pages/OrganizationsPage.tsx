import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { ApiError } from '../services/apiClient';
import { createOrganization, listMyOrganizations } from '../services/organizationService';
import type { Organization } from '../types/api';

function slugSuggestion(value: string): string {
  const latin = value.toLocaleLowerCase().replace(/[а-яё]/g, (letter) => ({
    а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z', и: 'i', й: 'i',
    к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f',
    х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
  }[letter] ?? ''));
  return latin.replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 180);
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Сессия истекла. Войдите в аккаунт ещё раз.';
    if (error.status === 403) return 'Для этого действия недостаточно прав.';
    if (error.status === 404) return 'Данные больше недоступны. Обновите страницу.';
    if (error.status === 409) return error.message;
    return error.message;
  }
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.';
}

export function OrganizationsPage() {
  const { token } = useAuthToken();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [slugEdited, setSlugEdited] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const result = await listMyOrganizations(token);
      setOrganizations(result.items);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); /* initial load only */ }, [token]);

  const submit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const organization = await createOrganization(token, name.trim(), slug.trim());
      setOrganizations((current) => [organization, ...current]);
      setName('');
      setSlug('');
      setSlugEdited(false);
      setNotice('Организация создана. Вы назначены её владельцем.');
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="page organization-page">
      <header className="page__heading organization-hero">
        <p className="eyebrow">Корпоративное обучение</p>
        <h1 className="page__title">Организации</h1>
        <p className="muted">Участники, приглашения, курсы и прогресс команды — в одном месте.</p>
      </header>

      {error && <p className="alert alert--error" role="alert">{error}</p>}
      {notice && <p className="alert alert--success" role="status">{notice}</p>}

      <section className="organization-list-section" aria-labelledby="organization-list-title">
        <div className="section-heading">
          <div><p className="eyebrow">Ваши пространства</p><h2 id="organization-list-title">Мои организации</h2></div>
          <span className="organization-count">{organizations.length}</span>
        </div>
        {loading ? <p className="muted" role="status">Загружаем организации…</p> : organizations.length === 0 ? (
          <div className="organization-empty card">
            <span className="organization-empty__icon" aria-hidden="true">⌂</span>
            <h3>Пока нет организаций</h3>
            <p className="muted">Создайте организацию или примите приглашение, чтобы начать корпоративное обучение.</p>
            <Link className="button button--ghost" to="/organizations/invitations/accept">Принять приглашение</Link>
          </div>
        ) : (
          <div className="organization-grid">
            {organizations.map((organization) => (
              <article className="organization-card card" key={organization.id}>
                <div className="organization-card__mark" aria-hidden="true">{organization.name.trim().charAt(0).toLocaleUpperCase()}</div>
                <div className="organization-card__body">
                  <div className="organization-card__title-row">
                    <h3>{organization.name}</h3>
                    <span className={`status-pill status-pill--${organization.status}`}>{organization.status === 'active' ? 'Активна' : organization.status === 'suspended' ? 'Приостановлена' : 'В архиве'}</span>
                  </div>
                  <p className="muted">Создана {new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(organization.created_at))}</p>
                  <Link className="button button--primary button--sm" to={`/organizations/${organization.id}`}>Открыть кабинет</Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="card organization-create" aria-labelledby="organization-create-title">
        <div><p className="eyebrow">Новое пространство</p><h2 id="organization-create-title">Создать организацию</h2><p className="muted">Вы станете владельцем и сможете приглашать сотрудников.</p></div>
        <form className="organization-create__form" onSubmit={(event) => void submit(event)}>
          <label className="field"><span className="field__label">Название</span>
            <input className="input" required minLength={2} maxLength={160} value={name} disabled={saving} onChange={(event) => {
              const next = event.target.value; setName(next);
              if (!slugEdited) setSlug(slugSuggestion(next));
            }} placeholder="Например, Школа Вектора" />
          </label>
          <label className="field"><span className="field__label">Адрес организации</span>
            <div className="organization-slug-field"><span> /organizations/</span><input className="input" required minLength={2} maxLength={180} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={slug} disabled={saving} onChange={(event) => {
              setSlugEdited(true); setSlug(slugSuggestion(event.target.value));
            }} placeholder="vektor-team" /></div>
            <span className="field__hint">Латинские буквы, цифры и дефисы.</span>
          </label>
          <button type="submit" className="button button--primary" disabled={saving || !name.trim() || !slug.trim()}>{saving ? 'Создаём…' : 'Создать организацию'}</button>
        </form>
      </section>
    </main>
  );
}

function useAuthToken(): { token: string } {
  const { token, status } = useAuth();
  if (status !== 'authenticated' || token === null) throw new Error('OrganizationsPage requires an authenticated route.');
  return { token };
}
