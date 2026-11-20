import type { ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useCallback, useEffect, useState } from 'react';

import logoUrl from '../assets/logo.svg';
import { useAuth } from '../auth/AuthContext';
import { useTheme } from '../theme/ThemeContext';
import { getUnreadCount } from '../services/notificationService';
import './Layout.css';

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? 'site-header__link site-header__link--active' : 'site-header__link';
}

export function AppLayout({ children }: { children: ReactNode }) {
  const { status, user, signOut } = useAuth();
  const { token } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);
  const refreshUnread = useCallback(() => {
    if (!token || status !== 'authenticated') { setUnreadCount(0); return; }
    void getUnreadCount(token).then(result => setUnreadCount(result.unread_count)).catch(() => undefined);
  }, [status, token]);
  useEffect(() => { refreshUnread(); }, [refreshUnread, location.pathname]);
  useEffect(() => {
    const onVisible = () => { if (document.visibilityState === 'visible') refreshUnread(); };
    window.addEventListener('notifications:refresh', refreshUnread);
    document.addEventListener('visibilitychange', onVisible);
    return () => { window.removeEventListener('notifications:refresh', refreshUnread); document.removeEventListener('visibilitychange', onVisible); };
  }, [refreshUnread]);
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

        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Тёмная тема"
          aria-pressed={theme === 'dark'}
          title={`Переключить тему, сейчас: ${theme === 'dark' ? 'тёмная' : 'светлая'}`}
        >
          <span aria-hidden="true">{theme === 'dark' ? '☼' : '◐'}</span>
          <span className="theme-toggle__label">{theme === 'dark' ? 'Светлая' : 'Тёмная'}</span>
        </button>

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
              {user.permissions.includes('notifications:read_own') && (
                <NavLink to="/notifications" className={navLinkClass} aria-label={`Уведомления, непрочитанных: ${unreadCount}`}>
                  Уведомления{unreadCount > 0 && <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>}
                </NavLink>
              )}
              {user.permissions.includes('certificates:read_self') && (
                <NavLink to="/certificates" className={navLinkClass}>
                  Сертификаты
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
