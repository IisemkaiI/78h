import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { getNotifications, markAllNotificationsRead, markNotificationRead, type NotificationItem, type NotificationPage as NotificationPageData } from '../services/notificationService';
import './NotificationsPage.css';

function targetFor(item: NotificationItem): string | null {
  if (item.type === 'course_completed' && typeof item.payload.course_slug === 'string') return `/learn/${encodeURIComponent(item.payload.course_slug)}`;
  if ((item.type === 'quiz_completed' || item.type.startsWith('assignment_')) && typeof item.payload.course_slug === 'string') return `/learn/${encodeURIComponent(item.payload.course_slug)}`;
  if (item.type === 'certificate_issued') return '/certificates';
  return null;
}

export function NotificationsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<NotificationPageData | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async (currentPage: number) => {
    if (!token) return;
    setBusy(true); setError('');
    try { setData(await getNotifications(token, currentPage)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось загрузить уведомления.'); }
    finally { setBusy(false); }
  }, [token]);
  useEffect(() => { void load(page); }, [load, page]);
  useEffect(() => { window.dispatchEvent(new Event('notifications:refresh')); }, []);

  const markOne = async (item: NotificationItem) => {
    if (!token || item.read_at) return;
    try {
      await markNotificationRead(token, item.id);
      setData(current => current ? { ...current, items: current.items.map(row => row.id === item.id ? { ...row, read_at: new Date().toISOString() } : row), unread_count: Math.max(0, current.unread_count - 1) } : current);
      window.dispatchEvent(new Event('notifications:refresh'));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось отметить уведомление прочитанным.');
    }
  };
  const markAll = async () => {
    if (!token) return;
    try { await markAllNotificationsRead(token); await load(page); window.dispatchEvent(new Event('notifications:refresh')); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось обновить уведомления.'); }
  };

  return <main className="notifications-page">
    <header className="notifications-page__heading"><div><p className="eyebrow">Личный кабинет</p><h1>Уведомления</h1><p>Непрочитанных: <strong>{data?.unread_count ?? '—'}</strong></p></div>
      <button className="button button--secondary" type="button" onClick={() => void markAll()} disabled={!data?.unread_count || busy}>Отметить все прочитанными</button></header>
    {error && <div className="notifications-page__error" role="alert">{error} <button type="button" onClick={() => void load(page)}>Повторить</button></div>}
    {busy && !data ? <p role="status">Загрузка уведомлений…</p> : null}
    {data && data.items.length === 0 && !busy ? <section className="notifications-page__empty"><h2>Пока уведомлений нет</h2><p>Здесь появятся новости о вашем обучении.</p></section> : null}
    <section className="notifications-list" aria-label="Список уведомлений" aria-busy={busy}>
      {data?.items.map(item => { const target = targetFor(item); return <article key={item.id} className={`notification-card${item.read_at ? '' : ' notification-card--unread'}`}>
        <div className="notification-card__content"><div className="notification-card__top"><h2>{item.title}</h2><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('ru-RU')}</time></div><p>{item.body}</p>
          {target ? <Link to={target} onClick={() => void markOne(item)}>Открыть материал →</Link> : <span className="notification-card__unavailable">Связанный материал недоступен</span>}</div>
        {!item.read_at && <button type="button" className="notification-card__read" onClick={() => void markOne(item)}>Прочитано</button>}
      </article>; })}
    </section>
    {data && data.total > data.page_size && <nav className="notifications-pagination" aria-label="Страницы уведомлений"><button className="button button--secondary" disabled={page <= 1 || busy} onClick={() => setPage(value => value - 1)}>Назад</button><span>Страница {page} из {Math.ceil(data.total / data.page_size)}</span><button className="button button--secondary" disabled={page >= Math.ceil(data.total / data.page_size) || busy} onClick={() => setPage(value => value + 1)}>Дальше</button></nav>}
  </main>;
}
