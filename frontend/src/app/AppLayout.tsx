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
  const canAuthor = user?.permissions.includes('courses:create') ?? false;
  const canLearn = user?.permissions.includes('enrollments:read_own') ?? false;
  const canReview = user?.permissions.some((permission) => ['assessments:review', 'assessments:manage_own', 'assessments:manage_all'].includes(permission)) ?? false;

  const handleLogout = (): void => {
    signOut();
    navigate('/login', { replace: true });
  };

  return (
    <div className="shell">
      <header className="site-header">
        <Link to="/" className="site-header__brand">
          <span className="site-header__mark">
            <img src={logoUrl} alt="" width={30} height={30} />
          </span>
          <span className="site-header__wordmark">
            образование<span> / открытая платформа</span>
          </span>
        </Link>

        <nav className="site-header__nav" aria-label="Основная навигация">
          <NavLink to="/catalog" className={navLinkClass}>
            Каталог
          </NavLink>

          {status === 'authenticated' && user !== null ? (
            <>
              {canLearn && (
                <NavLink to="/my-learning" className={navLinkClass}>
                  Моё обучение
                </NavLink>
              )}
              {canAuthor && (
                <NavLink to="/author" className={navLinkClass}>
                  Мои курсы
                </NavLink>
              )}
              {canReview && (
                <NavLink to="/teaching/reviews" className={navLinkClass}>
                  Работы
                </NavLink>
              )}
              <div className="site-header__account">
                <NavLink
                  to="/profile"
                  className="site-header__profile"
                  aria-label={`Профиль: ${user.display_name}`}
                >
                  <span className="site-header__avatar" aria-hidden="true">
                    {user.display_name.slice(0, 1).toLocaleUpperCase()}
                  </span>
                  <span>{user.display_name}</span>
                </NavLink>
                <button
                  type="button"
                  className="site-header__logout"
                  onClick={handleLogout}
                >
                  Выйти
                </button>
              </div>
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

      <div className="shell__content">{children}</div>
      <footer className="site-footer">
        <Link to="/" className="site-footer__brand">
          образование <span>для каждого</span>
        </Link>
        <span>Бесплатное обучение, открытое всем.</span>
        <Link to="/catalog">Исследовать каталог ↗</Link>
      </footer>
    </div>
  );
}
