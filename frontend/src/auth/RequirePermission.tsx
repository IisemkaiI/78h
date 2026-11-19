import type { ReactNode } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from './AuthContext';

/**
 * Client-side permission guard. It only improves the experience — the API
 * remains the authority for every operation.
 */
export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: ReactNode;
}) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <main className="page page--centered">
        <p className="page__status" role="status">
          Проверка сессии…
        </p>
      </main>
    );
  }

  if (status === 'anonymous' || user === null) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (!user.permissions.includes(permission)) {
    return (
      <main className="page page--centered">
        <div className="card stack" style={{ maxWidth: '32rem' }}>
          <p className="eyebrow">Доступ ограничен</p>
          <h1 className="page__title">Недостаточно прав</h1>
          <p className="muted">
            Для этого раздела нужна роль автора курсов. Роли назначаются администратором
            платформы.
          </p>
          <Link className="button button--ghost" to="/">
            На главную
          </Link>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
