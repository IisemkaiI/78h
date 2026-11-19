import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

/**
 * Redirects unauthenticated visitors to `/login`, remembering where they were
 * going. Frontend guards are UX only; the API protects its own endpoints.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();
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

  if (status === 'anonymous') {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}
