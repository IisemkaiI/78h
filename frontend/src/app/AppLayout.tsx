import type { ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useCallback, useEffect, useState } from 'react';

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
            <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
              <path d="M5 7.5c3.7-1.6 7.5-1.1 11 1.2 3.5-2.3 7.3-2.8 11-1.2v17c-3.7-1.6-7.5-1.1-11 1.2-3.5-2.3-7.3-2.8-11-1.2v-17Z" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
              <path d="M16 9v16M8.5 12c2-.5 3.7-.2 5 .7m5.5-.7c2-.5 3.7-.2 5 .7M8.5 16c2-.5 3.7-.2 5 .7m5.5-.7c2-.5 3.7-.2 5 .7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
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
              <NavLink to="/organizations" className={navLinkClass}>
                Организации
              </NavLink>
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
              {user.permissions.includes('admin:manage_platform') && <NavLink to="/admin" className={navLinkClass}>Администрирование</NavLink>}
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
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'}
            aria-pressed={theme === 'dark'}
            title={theme === 'dark' ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'}
          >
            {theme === 'dark' ? (
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20.5 15.3A8.5 8.5 0 0 1 8.7 3.5 8.5 8.5 0 1 0 20.5 15.3Z" /></svg>
            )}
          </button>
        </nav>
      </header>

      <div className="shell__content">{children}</div>
      <footer className="site-footer">
        <Link to="/" className="site-footer__brand">
          Вектор <span>учись, пробуй, создавай</span>
        </Link>
        <span>Проект «Вектор» создан в учебных целях.</span>
        <Link to="/catalog">Исследовать каталог ↗</Link>
      </footer>
    </div>
  );
}
