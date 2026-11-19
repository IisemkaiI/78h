import type { ReactNode } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';

import logoUrl from '../assets/logo.svg';
import { useAuth } from '../auth/AuthContext';
import './Layout.css';

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? 'site-header__link site-header__link--active' : 'site-header__link';
}

export function AppLayout({ children }: { children: ReactNode }) {
  const { status, user, signOut } = useAuth();
  const navigate = useNavigate();

  const handleLogout = (): void => {
    signOut();
    navigate('/login', { replace: true });
  };

  return (
    <div className="shell">
      <header className="site-header">
        <Link to="/" className="site-header__brand">
          <img src={logoUrl} alt="" width={28} height={28} />
          <span>Education Platform</span>
        </Link>

        <nav className="site-header__nav" aria-label="Основная навигация">
          {status === 'authenticated' && user !== null ? (
            <>
              <NavLink to="/profile" className={navLinkClass}>
                {user.display_name}
              </NavLink>
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={handleLogout}
              >
                Выйти
              </button>
            </>
          ) : status === 'loading' ? (
            <span className="site-header__muted" role="status">
              Загрузка…
            </span>
          ) : (
            <>
              <NavLink to="/login" className={navLinkClass}>
                Войти
              </NavLink>
              <Link to="/register" className="button button--primary button--sm">
                Регистрация
              </Link>
            </>
          )}
        </nav>
      </header>

      {children}
    </div>
  );
}
