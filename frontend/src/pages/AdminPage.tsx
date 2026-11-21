import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { ApiError } from '../services/apiClient';
import { archiveAdminCourse, getAdminOverview, listAdminCourses, listAdminOrganizations, listAdminUsers, setAdminUserActive } from '../services/adminService';
import { useAuth } from '../auth/AuthContext';
import type { AdminCourse, AdminOrganization, AdminOverview, AdminUser } from '../types/api';

type Tab = 'users' | 'courses' | 'organizations';

function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Сессия истекла. Войдите снова.';
    if (error.status === 403) return 'Недостаточно административных полномочий.';
    return error.message;
  }
  return 'Не удалось загрузить административные данные.';
}

export function AdminPage() {
  const { token } = useAuth();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [courses, setCourses] = useState<AdminCourse[]>([]);
  const [organizations, setOrganizations] = useState<AdminOrganization[]>([]);
  const [tab, setTab] = useState<Tab>('users');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError(null);
    try {
      const [stats, userPage, coursePage, orgRows] = await Promise.all([
        getAdminOverview(token), listAdminUsers(token, search), listAdminCourses(token, search), listAdminOrganizations(token),
      ]);
      setOverview(stats); setUsers(userPage.items); setCourses(coursePage.items); setOrganizations(orgRows);
    } catch (caught) { setError(message(caught)); }
    finally { setLoading(false); }
  }, [token, search]);

  useEffect(() => { void load(); }, [load]);

  const toggleUser = async (user: AdminUser) => {
    if (!window.confirm(`${user.is_active ? 'Отключить' : 'Включить'} аккаунт ${user.email}?`)) return;
    setPending(user.id); setError(null); setNotice(null);
    try { await setAdminUserActive(token!, user.id, !user.is_active); setNotice('Статус пользователя обновлён.'); await load(); }
    catch (caught) { setError(message(caught)); }
    finally { setPending(null); }
  };

  const archiveCourse = async (course: AdminCourse) => {
    if (!window.confirm(`Архивировать курс «${course.title}»? Существующие записи и прогресс сохранятся.`)) return;
    setPending(course.id); setError(null); setNotice(null);
    try { await archiveAdminCourse(token!, course.id); setNotice('Курс архивирован.'); await load(); }
    catch (caught) { setError(message(caught)); }
    finally { setPending(null); }
  };

  return <main className="page admin-page">
    <header className="admin-hero"><p className="eyebrow">Платформа · управление</p><h1>Панель администратора</h1><p className="muted">Сводка и базовое управление пользователями, курсами и организациями.</p></header>
    {error && <p className="alert alert--error" role="alert">{error}</p>}{notice && <p className="alert alert--success" role="status">{notice}</p>}
    {overview && <section className="admin-stats" aria-label="Статистика платформы">
      {[["Пользователи", overview.users_total], ["Организации", overview.organizations_total], ["Курсы", overview.courses_total], ["Назначения", overview.assignments_total], ["Ожидают", overview.assignments_pending], ["Принятые назначения", overview.assignments_accepted], ["Завершённые курсы", overview.completed_courses], ["Средний прогресс", `${overview.average_progress_percent}%`]].map(([label, value]) => <article className="card admin-stat" key={label}><span>{label}</span><strong>{value}</strong></article>)}
    </section>}
    <div className="admin-controls"><nav className="organization-tabs" aria-label="Административные разделы">{([['users','Пользователи'],['courses','Курсы'],['organizations','Организации']] as const).map(([id,label]) => <button key={id} type="button" className={tab === id ? 'organization-tabs__tab is-active' : 'organization-tabs__tab'} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {tab !== 'organizations' && <label className="field admin-search"><span className="field__label">Поиск</span><input className="input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={tab === 'users' ? 'Имя или email' : 'Название курса'} /></label>}
    </div>
    {loading ? <p className="page__status" role="status">Загрузка административных данных…</p> : tab === 'users' ? <TableShell title="Пользователи" empty={!users.length}>
      {users.map((item) => <div className="admin-row admin-row--users" key={item.id}><div><strong>{item.display_name}</strong><small>{item.email}</small></div><span>{item.roles.join(', ')}</span><span className={`status-pill status-pill--${item.is_active ? 'active' : 'suspended'}`}>{item.is_active ? 'Активен' : 'Отключён'}</span><button className={`button button--sm ${item.is_active ? 'button--danger' : 'button--ghost'}`} disabled={pending !== null} onClick={() => void toggleUser(item)}>{item.is_active ? 'Отключить' : 'Включить'}</button></div>)}
    </TableShell> : tab === 'courses' ? <TableShell title="Курсы" empty={!courses.length}>
      {courses.map((item) => <div className="admin-row admin-row--courses" key={item.id}><div><strong>{item.title}</strong><small>{item.author_name} · /{item.slug}</small></div><span className={`status-pill status-pill--${item.status === 'published' ? 'active' : item.status === 'archived' ? 'archived' : 'pending'}`}>{item.status}</span>{item.status !== 'archived' && <button className="button button--danger button--sm" disabled={pending !== null} onClick={() => void archiveCourse(item)}>Архивировать</button>}</div>)}
    </TableShell> : <TableShell title="Организации" empty={!organizations.length}>
      {organizations.map((item) => <div className="admin-row admin-row--organizations" key={item.id}><div><strong>{item.name}</strong><small>/{item.slug}</small></div><span>{item.members_count} участников</span><span className={`status-pill status-pill--${item.status === 'active' ? 'active' : 'archived'}`}>{item.status}</span></div>)}
    </TableShell>}
  </main>;
}

function TableShell({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
  return <section className="card admin-table"><h2>{title}</h2>{empty ? <p className="muted">Ничего не найдено.</p> : children}</section>;
}
