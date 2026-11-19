import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { describeAuthError } from '../utils/authErrors';
import { formatDate, roleLabel } from '../utils/labels';
import { validateDisplayName } from '../utils/validation';
import './auth.css';

export function ProfilePage() {
  const { user, updateDisplayName, signOut } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState(user?.display_name ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setDisplayName(user?.display_name ?? '');
  }, [user?.display_name]);

  if (user === null) {
    return (
      <main className="page page--centered">
        <p className="page__status" role="status">
          Загрузка профиля…
        </p>
      </main>
    );
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    const validationError = validateDisplayName(displayName);
    if (validationError !== null) {
      setError(validationError);
      setSaved(false);
      return;
    }

    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateDisplayName(displayName.trim());
      setSaved(true);
    } catch (caught) {
      setError(describeAuthError(caught));
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = (): void => {
    signOut();
    navigate('/login', { replace: true });
  };

  const initial = user.display_name.trim().charAt(0).toUpperCase() || '?';

  return (
    <main className="page">
      <header className="page__heading">
        <p className="eyebrow">Личный профиль</p>
        <h1 className="page__title">{user.display_name}</h1>
        <p className="muted">Данные аккаунта и назначенные роли.</p>
      </header>

      <div className="profile-layout">
        <div className="profile-layout__main">
          <section className="card stack" aria-labelledby="profile-edit-title">
            <div className="profile__header">
              <h2 id="profile-edit-title">Изменить имя</h2>
              <div className="profile__identity">
                <span className="profile__avatar" aria-hidden="true">
                  {initial}
                </span>
              </div>
            </div>

            {error !== null && (
              <p className="alert alert--error" role="alert">
                {error}
              </p>
            )}
            {saved && (
              <p className="alert alert--success" role="status">
                Имя сохранено.
              </p>
            )}

            <form className="form" onSubmit={handleSubmit} noValidate>
              <label className="field">
                <span className="field__label">Отображаемое имя</span>
                <input
                  className="input"
                  type="text"
                  name="display_name"
                  value={displayName}
                  onChange={(event) => {
                    setDisplayName(event.target.value);
                    setSaved(false);
                  }}
                  disabled={saving}
                  aria-invalid={error !== null}
                />
                <span className="field__hint">
                  UUID, email, роли и права доступа изменяются только на стороне платформы.
                </span>
              </label>

              <button type="submit" className="button button--primary" disabled={saving}>
                {saving ? 'Сохранение…' : 'Сохранить'}
              </button>
            </form>
          </section>

          <section className="card stack" aria-labelledby="profile-roles-title">
            <h2 id="profile-roles-title">Роли</h2>
            <div className="badge-row">
              {user.roles.map((role) => (
                <span key={role.code} className="badge badge--role" title={role.name}>
                  {roleLabel(role.code)}
                </span>
              ))}
            </div>

            <div className="profile__permissions">
              <details>
                <summary>Разрешения ({user.permissions.length})</summary>
                <ul className="profile__permission-list">
                  {user.permissions.map((permission) => (
                    <li key={permission}>
                      <code>{permission}</code>
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          </section>
        </div>

        <aside className="card stack" aria-labelledby="profile-details-title">
          <h2 id="profile-details-title">Данные аккаунта</h2>
          <dl className="definition-list">
            <div>
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
            <div>
              <dt>UUID</dt>
              <dd>
                <code>{user.id}</code>
              </dd>
            </div>
            <div>
              <dt>Дата регистрации</dt>
              <dd>{formatDate(user.created_at)}</dd>
            </div>
            <div>
              <dt>Статус</dt>
              <dd>{user.is_active ? 'Активен' : 'Деактивирован'}</dd>
            </div>
          </dl>

          <div className="profile__actions">
            <button type="button" className="button button--ghost" onClick={handleLogout}>
              Выйти из аккаунта
            </button>
          </div>
        </aside>
      </div>
    </main>
  );
}
