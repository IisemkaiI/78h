import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { canLeaveOrganization, canManageMember, canRevokeInvitation, editableMemberRoles, invitationRoles } from '../organizations/policy';
import { ApiError } from '../services/apiClient';
import { listCatalogCourses } from '../services/catalogService';
import {
  createOrganizationDepartment,
  deleteOrganizationDepartment,
  listOrganizationDepartments,
  renameOrganizationDepartment,
  setMemberDepartment,
  acceptCorporateAssignment,
  cancelCorporateAssignment,
  createCorporateAssignments,
  createInvitation,
  declineCorporateAssignment,
  getOrganization,
  getOrganizationLearningStats,
  leaveOrganization,
  listCorporateAssignments,
  listInvitations,
  listOrganizationMembers,
  removeOrganizationMember,
  revokeInvitation,
  updateMemberRole,
} from '../services/organizationService';
import type {
  CatalogCourse,
  CorporateAssignment,
  InvitationRole,
  Organization,
  OrganizationInvitation,
  OrganizationLearningStats,
  OrganizationDepartment,
  OrganizationMembership,
  OrganizationRole,
} from '../types/api';

type CabinetTab = 'overview' | 'members' | 'departments' | 'invitations' | 'learning';

const roleLabels: Record<OrganizationRole, string> = {
  owner: 'Владелец', admin: 'Администратор', manager: 'Менеджер', employee: 'Сотрудник',
};
const assignmentLabels = {
  pending: 'Ожидает ответа', accepted: 'Принято', declined: 'Отклонено', cancelled: 'Отменено',
} as const;

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Сессия истекла. Войдите в аккаунт ещё раз.';
    if (error.status === 403) return 'Backend отказал в доступе: для этой операции недостаточно полномочий.';
    if (error.status === 404) return 'Организация или запись больше не найдена либо недоступна.';
    if (error.status === 409) return error.message;
    return error.message;
  }
  return 'Не удалось выполнить запрос. Проверьте соединение и повторите попытку.';
}

function dateText(value: string | null): string {
  if (value === null) return 'Без срока';
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function isManagerRole(role: OrganizationRole | 'platform_admin' | null): role is 'owner' | 'admin' | 'manager' {
  return role === 'owner' || role === 'admin' || role === 'manager';
}

export function OrganizationCabinetPage() {
  const { organizationId = '' } = useParams();
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [role, setRole] = useState<OrganizationRole | 'platform_admin' | null>(null);
  const [members, setMembers] = useState<OrganizationMembership[]>([]);
  const [departments, setDepartments] = useState<OrganizationDepartment[]>([]);
  const [departmentName, setDepartmentName] = useState('');
  const [departmentDrafts, setDepartmentDrafts] = useState<Record<string, string>>({});
  const [invitations, setInvitations] = useState<OrganizationInvitation[]>([]);
  const [assignments, setAssignments] = useState<CorporateAssignment[]>([]);
  const [stats, setStats] = useState<OrganizationLearningStats | null>(null);
  const [courses, setCourses] = useState<CatalogCourse[]>([]);
  const [courseTotalPages, setCourseTotalPages] = useState(0);
  const [coursePage, setCoursePage] = useState(1);
  const [courseSearch, setCourseSearch] = useState('');
  const [tab, setTab] = useState<CabinetTab>('overview');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<InvitationRole>('employee');
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [roleDrafts, setRoleDrafts] = useState<Record<string, OrganizationRole>>({});
  const [selectedCourseId, setSelectedCourseId] = useState('');
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
  const [dueDate, setDueDate] = useState('');
  const [requiredAssignment, setRequiredAssignment] = useState(true);

  const canManage = isManagerRole(role);
  const isOwner = role === 'owner';
  const employeeMembers = useMemo(() => members.filter((member) => member.role === 'employee'), [members]);
  const activeOwnerCount = useMemo(() => members.filter((member) => member.role === 'owner' && member.status === 'active').length, [members]);

  const load = useCallback(async (silent = false): Promise<void> => {
    if (!organizationId || !token) return;
    if (!silent) setLoading(true);
    setError(null);
    try {
      const org = await getOrganization(token, organizationId);
      setOrganization(org);
      let memberRows: OrganizationMembership[] = [];
      let inferredRole: OrganizationRole | 'platform_admin' | null = null;
      try {
        memberRows = await listOrganizationMembers(token, organizationId);
        const ownMembership = memberRows.find((member) => member.user_id === user?.id);
        inferredRole = ownMembership?.role ?? 'platform_admin';
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 403) inferredRole = 'employee';
        else throw caught;
      }
      setRole(inferredRole);
      setMembers(memberRows);
      const assignmentResult = await listCorporateAssignments(token, organizationId);
      setAssignments(assignmentResult.items);
      if (isManagerRole(inferredRole)) {
        const [inviteResult, statsResult, departmentRows] = await Promise.all([
          listInvitations(token, organizationId),
          getOrganizationLearningStats(token, organizationId),
          listOrganizationDepartments(token, organizationId),
        ]);
        setInvitations(inviteResult.items);
        setStats(statsResult);
        setDepartments(departmentRows);
      } else {
        setInvitations([]);
        setStats(null);
        setDepartments([]);
      }
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      if (!silent) setLoading(false);
    }
  }, [organizationId, token, user?.id]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!canManage || !token) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void listCatalogCourses({ search: courseSearch, page: coursePage, pageSize: 24, sort: 'newest' }, controller.signal)
        .then((result) => { setCourses(result.items); setCourseTotalPages(result.pages); })
        .catch((caught: unknown) => { if (!controller.signal.aborted) setError(errorText(caught)); });
    }, courseSearch ? 250 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [canManage, coursePage, courseSearch, token]);

  const perform = async (key: string, successMessage: string, operation: () => Promise<unknown>): Promise<void> => {
    setBusyAction(key);
    setError(null);
    setNotice(null);
    try {
      await operation();
      setNotice(successMessage);
      await load(true);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusyAction(null);
    }
  };

  const submitInvitation = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setSaving(true); setError(null); setNotice(null); setCreatedToken(null);
    try {
      const invitation = await createInvitation(token!, organizationId, inviteEmail.trim(), inviteRole);
      setCreatedToken(invitation.token ?? null);
      setInviteEmail('');
      setNotice('Приглашение создано. Скопируйте одноразовый токен и передайте его сотруднику.');
      await load(true);
    } catch (caught) { setError(errorText(caught)); }
    finally { setSaving(false); }
  };

  const submitAssignments = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (!selectedCourseId || selectedMembers.length === 0) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      const dueAt = dueDate ? new Date(`${dueDate}T23:59:59`).toISOString() : null;
      await createCorporateAssignments(token!, organizationId, selectedCourseId, selectedMembers, dueAt, requiredAssignment);
      setSelectedMembers([]); setSelectedCourseId(''); setDueDate('');
      setNotice(`Назначение создано для ${selectedMembers.length} ${selectedMembers.length === 1 ? 'сотрудника' : 'сотрудников'}.`);
      await load(true);
    } catch (caught) { setError(errorText(caught)); }
    finally { setSaving(false); }
  };

  const handleRoleChange = async (member: OrganizationMembership): Promise<void> => {
    const nextRole = roleDrafts[member.id];
    if (!nextRole || nextRole === member.role) return;
    await perform(`role:${member.id}`, 'Роль участника обновлена.', () => updateMemberRole(token!, organizationId, member.id, nextRole));
  };

  const handleDepartmentCreate = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (!departmentName.trim()) return;
    await perform('department:create', 'Подразделение создано.', async () => {
      await createOrganizationDepartment(token!, organizationId, departmentName.trim());
      setDepartmentName('');
    });
  };

  const handleCopy = async (): Promise<void> => {
    if (!createdToken) return;
    try {
      await navigator.clipboard.writeText(createdToken);
      setNotice('Токен скопирован. Он больше не будет показан после ухода со страницы.');
    } catch {
      setError('Браузер запретил доступ к буферу обмена. Выделите и скопируйте токен вручную.');
    }
  };

  const handleLeave = async (): Promise<void> => {
    if (!window.confirm('Выйти из организации? Ваш личный прогресс обучения сохранится.')) return;
    setBusyAction('leave'); setError(null); setNotice(null);
    try {
      await leaveOrganization(token!, organizationId);
      navigate('/organizations', { replace: true });
    } catch (caught) { setError(errorText(caught)); }
    finally { setBusyAction(null); }
  };

  if (loading) return <main className="page page--centered"><p className="page__status" role="status">Загружаем корпоративный кабинет…</p></main>;
  if (!organization) return <main className="page"><Link to="/organizations" className="text-link">← К организациям</Link><p className="alert alert--error" role="alert">{error ?? 'Организация не найдена.'}</p></main>;

  const availableTabs: { id: CabinetTab; label: string }[] = [
    { id: 'overview', label: 'Обзор' },
    ...(canManage ? [{ id: 'members' as const, label: `Участники${members.length ? ` · ${members.length}` : ''}` }, { id: 'departments' as const, label: `Подразделения${departments.length ? ` · ${departments.length}` : ''}` }, { id: 'invitations' as const, label: 'Приглашения' }] : []),
    { id: 'learning', label: `Обучение${assignments.length ? ` · ${assignments.length}` : ''}` },
  ];

  const memberCanBeManaged = (member: OrganizationMembership): boolean => canManageMember(role, member, user?.id, activeOwnerCount);
  const rolesForMember = (member: OrganizationMembership): OrganizationRole[] => member.can_update_role
    ? editableMemberRoles(role, member.role, activeOwnerCount)
    : [];
  const inviteRoles: InvitationRole[] = invitationRoles(role);

  return (
    <main className="page organization-page">
      <Link to="/organizations" className="text-link">← Мои организации</Link>
      <header className="organization-dashboard-hero">
        <div className="organization-dashboard-hero__mark" aria-hidden="true">{organization.name.trim().charAt(0).toLocaleUpperCase()}</div>
        <div className="organization-dashboard-hero__copy">
          <p className="eyebrow">Корпоративный кабинет</p>
          <h1>{organization.name}</h1>
          <p className="muted">{role ? role === 'platform_admin' ? 'Платформенный администратор' : roleLabels[role] : 'Участник организации'} · {organization.slug}</p>
        </div>
        {canLeaveOrganization(role, activeOwnerCount) && <button className="button button--ghost organization-leave" disabled={busyAction !== null} onClick={() => void handleLeave()}>Выйти из организации</button>}
      </header>
      {isOwner && activeOwnerCount <= 1 && <p className="alert alert--info" role="status">В организации должен остаться хотя бы один владелец. Назначьте другого владельца, прежде чем выйти или снять эту роль.</p>}

      {error && <p className="alert alert--error" role="alert">{error}</p>}
      {notice && <p className="alert alert--success" role="status">{notice}</p>}

      <nav className="organization-tabs" aria-label="Разделы организации">
        {availableTabs.map((item) => <button key={item.id} type="button" className={tab === item.id ? 'organization-tabs__tab is-active' : 'organization-tabs__tab'} onClick={() => setTab(item.id)}>{item.label}</button>)}
      </nav>

      {tab === 'overview' && (
        <section className="organization-overview">
          {stats ? <div className="organization-stats-grid">
            <Stat label="Участники" value={employeeMembers.length} hint="Активные сотрудники организации" />
            <Stat label="Назначения" value={stats.assignments_total} hint={`${stats.accepted} приняты · ${stats.pending} ожидают`} />
            <Stat label="Завершённые курсы" value={stats.completed_enrollments} hint={`${stats.active_enrollments} сейчас проходят`} />
            <Stat label="Средний прогресс" value={`${stats.average_progress_percent}%`} hint="По связанным записям обучения" />
          </div> : <div className="card organization-empty"><h2>Добро пожаловать в {organization.name}</h2><p className="muted">Здесь появятся ваши корпоративные назначения и обучение.</p></div>}
          <div className="card organization-overview__next"><div><p className="eyebrow">Следующий шаг</p><h2>{canManage ? 'Соберите учебную программу команды' : 'Продолжите корпоративное обучение'}</h2><p className="muted">{canManage ? 'Пригласите сотрудников и назначьте им опубликованные курсы.' : 'Откройте список назначений, чтобы принять приглашённый курс или продолжить обучение.'}</p></div><button className="button button--primary" onClick={() => setTab(canManage ? 'invitations' : 'learning')}>{canManage ? 'К приглашениям' : 'Мои назначения'}</button></div>
        </section>
      )}

      {tab === 'members' && canManage && (
        <section className="organization-section stack">
          <div className="section-heading"><div><p className="eyebrow">Состав команды</p><h2>Участники</h2></div><span className="organization-count">{members.length}</span></div>
          {members.length === 0 ? <EmptyState title="Нет активных участников" description="Пригласите сотрудников, чтобы начать обучение команды." /> : <div className="organization-member-list card">
            {members.map((member) => {
              const mayManage = memberCanBeManaged(member);
              const roleOptions = rolesForMember(member);
              return <article className="organization-member" key={member.id}>
                <div className="organization-member__avatar" aria-hidden="true">{member.display_name.trim().charAt(0).toLocaleUpperCase()}</div>
                <div className="organization-member__identity"><strong>{member.display_name}{member.user_id === user?.id ? ' (вы)' : ''}</strong><span>{member.email}</span></div>
                <span className={`role-pill role-pill--${member.role}`}>{roleLabels[member.role]}</span>
                {mayManage && <div className="organization-member__actions">
                  {member.can_update_role && roleOptions.length > 0 && <><select className="input input--compact" aria-label={`Роль: ${member.display_name}`} value={roleDrafts[member.id] ?? member.role} onChange={(event) => setRoleDrafts((current) => ({ ...current, [member.id]: event.target.value as OrganizationRole }))}>{roleOptions.map((option) => <option key={option} value={option}>{roleLabels[option]}</option>)}</select><button className="button button--ghost button--sm" disabled={busyAction !== null || (roleDrafts[member.id] ?? member.role) === member.role} onClick={() => void handleRoleChange(member)}>Сохранить роль</button></>}
                  {member.can_remove && <button className="button button--danger button--sm" disabled={busyAction !== null} onClick={() => { if (window.confirm(`Удалить участника ${member.display_name} из организации?`)) void perform(`remove:${member.id}`, 'Участник удалён из организации.', () => removeOrganizationMember(token!, organizationId, member.id)); }}>Удалить</button>}
                </div>}
              </article>;
            })}
          </div>}
          <p className="field__hint">Изменение ролей и удаление участников дополнительно проверяются backend с учётом scoped RBAC.</p>
        </section>
      )}

      {tab === 'departments' && canManage && (
        <section className="organization-section stack">
          <div><p className="eyebrow">Структура команды</p><h2>Подразделения</h2><p className="muted">Плоский список подразделений в пределах этой организации.</p></div>
          {(role === 'owner' || role === 'admin') && <form className="organization-department-form card" onSubmit={(event) => void handleDepartmentCreate(event)}>
            <label className="field"><span className="field__label">Название подразделения</span><input className="input" value={departmentName} onChange={(event) => setDepartmentName(event.target.value)} minLength={2} maxLength={120} required disabled={saving} /></label>
            <button className="button button--primary" disabled={saving || departmentName.trim().length < 2}>{saving ? 'Создаём…' : 'Создать подразделение'}</button>
          </form>}
          {departments.length === 0 ? <EmptyState title="Подразделений пока нет" description="Создайте первое подразделение для группировки сотрудников." /> : <div className="organization-department-list">
            {departments.map((department) => <article className="card organization-department" key={department.id}>
              <div className="organization-department__heading"><div><h3>{department.name}</h3><span className="muted">{department.members_count} участников</span></div>
                {(role === 'owner' || role === 'admin') && <div className="organization-member__actions"><input className="input input--compact" aria-label={`Новое название ${department.name}`} value={departmentDrafts[department.id] ?? department.name} onChange={(event) => setDepartmentDrafts((drafts) => ({ ...drafts, [department.id]: event.target.value }))} /><button className="button button--ghost button--sm" disabled={busyAction !== null || (departmentDrafts[department.id] ?? department.name).trim().length < 2 || (departmentDrafts[department.id] ?? department.name) === department.name} onClick={() => { const newName = (departmentDrafts[department.id] ?? department.name).trim(); void perform(`department:${department.id}`, 'Название подразделения обновлено.', () => renameOrganizationDepartment(token!, organizationId, department.id, newName)); }}>Сохранить</button><button className="button button--danger button--sm" disabled={busyAction !== null} onClick={() => { if (window.confirm(`Удалить подразделение «${department.name}»? Сотрудники останутся в организации без подразделения.`)) void perform(`department:delete:${department.id}`, 'Подразделение удалено.', () => deleteOrganizationDepartment(token!, organizationId, department.id)); }}>Удалить</button></div>}
              </div>
              <div className="organization-department__members">{members.filter((member) => member.department_id === department.id).map((member) => <div className="organization-department__member" key={member.id}><span>{member.display_name}</span><small>{member.email}</small>{canManage && <select className="input input--compact" aria-label={`Подразделение: ${member.display_name}`} value={member.department_id ?? ''} disabled={busyAction !== null} onChange={(event) => void perform(`member-department:${member.id}`, 'Подразделение участника обновлено.', () => setMemberDepartment(token!, organizationId, member.id, event.target.value || null))}><option value="">Без подразделения</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}</div>)}</div>
            </article>)}
          </div>}
          <h3>Без подразделения</h3>
          <div className="organization-department__members">{members.filter((member) => member.department_id === null).map((member) => <div className="organization-department__member" key={member.id}><span>{member.display_name}</span><small>{member.email}</small><select className="input input--compact" aria-label={`Подразделение: ${member.display_name}`} disabled={busyAction !== null || departments.length === 0} value="" onChange={(event) => void perform(`member-department:${member.id}`, 'Подразделение участника обновлено.', () => setMemberDepartment(token!, organizationId, member.id, event.target.value || null))}><option value="">Выбрать подразделение</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>)}</div>
        </section>
      )}

      {tab === 'invitations' && canManage && (
        <section className="organization-section stack">
          <div><p className="eyebrow">Доступ в команду</p><h2>Приглашения</h2><p className="muted">Приглашайте только зарегистрированные аккаунты. Ссылка или токен передаются вручную.</p></div>
          <form className="card organization-form" onSubmit={(event) => void submitInvitation(event)}>
            <label className="field"><span className="field__label">Email существующего аккаунта</span><input className="input" type="email" required maxLength={320} value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} disabled={saving} placeholder="colleague@example.com" /></label>
            <label className="field"><span className="field__label">Роль в организации</span><select className="input" value={inviteRole} onChange={(event) => setInviteRole(event.target.value as InvitationRole)} disabled={saving}>{inviteRoles.map((item) => <option key={item} value={item}>{roleLabels[item]}</option>)}</select></label>
            <button className="button button--primary" disabled={saving || !inviteEmail.trim()}>{saving ? 'Создаём приглашение…' : 'Создать приглашение'}</button>
          </form>
          {createdToken && <div className="organization-token card"><div><p className="eyebrow">Одноразовый токен</p><p>Передайте его сотруднику доверенным способом. Повторно получить этот токен нельзя.</p><code>{createdToken}</code></div><button className="button button--ghost" onClick={() => void handleCopy()}>Копировать токен</button></div>}
          <div className="section-heading"><div><p className="eyebrow">История доступа</p><h3>Выданные приглашения</h3></div></div>
          {invitations.length === 0 ? <EmptyState title="Приглашений пока нет" description="Создайте приглашение для сотрудника выше." /> : <div className="organization-invitation-list card">
            {invitations.map((invitation) => {
              const canRevoke = canRevokeInvitation(role, invitation.role, invitation.status);
              return <article className="organization-invitation" key={invitation.id}>
                <div><strong>{invitation.email}</strong><span>{roleLabels[invitation.role]} · создано {dateText(invitation.created_at)}</span></div>
                <span className={`status-pill status-pill--${invitation.status}`}>{invitation.status === 'pending' ? 'Ожидает · до ' + dateText(invitation.expires_at) : invitation.status === 'accepted' ? 'Принято' : invitation.status === 'expired' ? 'Истекло' : 'Отозвано'}</span>
                {canRevoke && <button className="button button--danger button--sm" disabled={busyAction !== null} onClick={() => { if (window.confirm(`Отозвать приглашение для ${invitation.email}?`)) void perform(`revoke:${invitation.id}`, 'Приглашение отозвано.', () => revokeInvitation(token!, organizationId, invitation.id)); }}>Отозвать</button>}
              </article>;
            })}
          </div>}
        </section>
      )}

      {tab === 'learning' && (
        <section className="organization-section stack">
          {canManage && <>
            <div><p className="eyebrow">План обучения</p><h2>Назначить курс сотрудникам</h2><p className="muted">Можно выбрать нескольких сотрудников. Назначение станет активным после принятия сотрудником.</p></div>
            <form className="card organization-assignment-form" onSubmit={(event) => void submitAssignments(event)}>
              <label className="field"><span className="field__label">Найти опубликованный курс</span><input className="input" value={courseSearch} onChange={(event) => { setCourseSearch(event.target.value); setCoursePage(1); }} placeholder="Название курса" /></label>
              <div className="field"><span className="field__label">Курс</span><select className="input" required value={selectedCourseId} onChange={(event) => setSelectedCourseId(event.target.value)}><option value="">Выберите курс</option>{courses.map((course) => <option value={course.id} key={course.id}>{course.title} · {course.category.name}</option>)}</select><div className="organization-course-pages"><span className="field__hint">{courses.length ? `Найдено на странице: ${courses.length}` : 'Опубликованные курсы не найдены.'}</span><div><button type="button" className="button button--ghost button--sm" disabled={coursePage <= 1} onClick={() => setCoursePage((page) => Math.max(1, page - 1))}>Назад</button><span>{coursePage}{courseTotalPages ? ` / ${courseTotalPages}` : ''}</span><button type="button" className="button button--ghost button--sm" disabled={courseTotalPages === 0 || coursePage >= courseTotalPages} onClick={() => setCoursePage((page) => page + 1)}>Далее</button></div></div></div>
              <fieldset className="organization-employee-picker"><legend>Сотрудники · выбрано {selectedMembers.length}</legend>{employeeMembers.length === 0 ? <p className="muted">Сначала добавьте сотрудников через приглашения.</p> : <><label className="organization-check"><input type="checkbox" checked={selectedMembers.length === Math.min(employeeMembers.length, 500) && employeeMembers.length > 0} onChange={(event) => setSelectedMembers(event.target.checked ? employeeMembers.slice(0, 500).map((member) => member.id) : [])} /><span>Выбрать всех сотрудников</span></label>{employeeMembers.length > 500 && <p className="field__hint">За один запрос можно выбрать до 500 сотрудников. Остальных назначьте отдельной группой.</p>}<div className="organization-employee-grid">{employeeMembers.map((member) => <label className="organization-check" key={member.id}><input type="checkbox" checked={selectedMembers.includes(member.id)} disabled={!selectedMembers.includes(member.id) && selectedMembers.length >= 500} onChange={(event) => setSelectedMembers((current) => event.target.checked ? [...current, member.id] : current.filter((id) => id !== member.id))} /><span>{member.display_name}<small>{member.email}</small></span></label>)}</div></>}</fieldset>
              <div className="organization-assignment-form__options"><label className="field"><span className="field__label">Срок выполнения</span><input className="input" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /></label><label className="organization-check organization-check--inline"><input type="checkbox" checked={requiredAssignment} onChange={(event) => setRequiredAssignment(event.target.checked)} /><span>Обязательное назначение</span></label></div>
              <button className="button button--primary" disabled={saving || !selectedCourseId || !selectedMembers.length}>{saving ? 'Назначаем…' : `Назначить ${selectedMembers.length || ''} сотрудникам`}</button>
            </form>
          </>}

          <div className="section-heading"><div><p className="eyebrow">Корпоративный процесс</p><h2>{canManage ? 'Назначения и прогресс' : 'Мои назначения'}</h2></div>{stats && <span className="organization-count">{stats.assignments_total}</span>}</div>
          {canManage && assignments.length > 0 && <div className="organization-report-table-wrap card"><table className="organization-report-table"><caption>Отчёт по назначенному обучению</caption><thead><tr><th>Сотрудник</th><th>Подразделение</th><th>Курс</th><th>Статус</th><th>Прогресс</th><th>Назначено</th></tr></thead><tbody>{assignments.map((assignment) => <tr key={`report:${assignment.id}`}><td data-label="Сотрудник">{assignment.learner_name}</td><td data-label="Подразделение">{departments.find((item) => item.id === assignment.department_id)?.name ?? '—'}</td><td data-label="Курс">{assignment.course_title}</td><td data-label="Статус">{assignment.overdue_at ? 'Просрочено' : assignmentLabels[assignment.status]}</td><td data-label="Прогресс">{assignment.progress_percent ?? 0}%</td><td data-label="Назначено">{dateText(assignment.assigned_at)}</td></tr>)}</tbody></table></div>}
          {assignments.length === 0 ? <EmptyState title="Назначений пока нет" description={canManage ? 'Выберите опубликованный курс и сотрудников, чтобы создать первое назначение.' : 'Когда организация назначит вам курс, он появится здесь.'} /> : <div className="organization-assignment-list">
            {assignments.map((assignment) => {
              const canRespond = role === 'employee' && assignment.status === 'pending';
              const canCancel = canManage && ['pending', 'accepted'].includes(assignment.status);
              return <article className="organization-assignment card" key={assignment.id}>
                <div className="organization-assignment__main"><div className="organization-assignment__title"><div><p className="eyebrow">{canManage ? assignment.learner_name : 'Курс организации'}</p><h3>{assignment.course_title}</h3></div><span className={`status-pill status-pill--${assignment.overdue_at ? 'suspended' : assignment.status}`}>{assignment.overdue_at ? 'Просрочено' : assignmentLabels[assignment.status]}</span></div>
                  <div className="organization-assignment__meta"><span>Назначено {dateText(assignment.assigned_at)}</span><span>Срок: {dateText(assignment.due_at)}</span>{canManage && <span>Подразделение: {departments.find((item) => item.id === assignment.department_id)?.name ?? 'Без подразделения'}</span>}{assignment.is_required && <span>Обязательный курс</span>}</div>
                  {assignment.enrollment_id && <div className="organization-progress"><div className="organization-progress__label"><span>{assignment.enrollment_status === 'cancelled' ? 'Личное обучение отменено' : assignment.is_course_completed ? 'Курс завершён' : 'Прогресс обучения'}</span><strong>{assignment.progress_percent ?? 0}%</strong></div><div className="organization-progress__track"><span style={{ width: `${assignment.progress_percent ?? 0}%` }} /></div></div>}
                </div>
                <div className="organization-assignment__actions">
                  {canRespond && <><button className="button button--primary button--sm" disabled={busyAction !== null} onClick={() => void perform(`accept:${assignment.id}`, 'Назначение принято. Курс добавлен в ваше обучение.', () => acceptCorporateAssignment(token!, organizationId, assignment.id))}>Принять курс</button><button className="button button--ghost button--sm" disabled={busyAction !== null} onClick={() => { if (window.confirm('Отклонить это назначение?')) void perform(`decline:${assignment.id}`, 'Назначение отклонено.', () => declineCorporateAssignment(token!, organizationId, assignment.id)); }}>Отклонить</button></>}
                  {canCancel && <button className="button button--danger button--sm" disabled={busyAction !== null} onClick={() => { if (window.confirm('Отменить корпоративное назначение? Личная запись и прогресс сотрудника сохранятся.')) void perform(`cancel:${assignment.id}`, 'Назначение отменено. Личный Enrollment не изменён.', () => cancelCorporateAssignment(token!, organizationId, assignment.id)); }}>Отменить назначение</button>}
                  {assignment.enrollment_id && assignment.enrollment_status === 'active' && <Link className="button button--ghost button--sm" to="/my-learning">Открыть обучение</Link>}
                </div>
              </article>;
            })}
          </div>}
        </section>
      )}
    </main>
  );
}

function Stat({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return <article className="organization-stat card"><span className="organization-stat__label">{label}</span><strong>{value}</strong><span className="muted">{hint}</span></article>;
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="organization-empty card"><span className="organization-empty__icon" aria-hidden="true">↗</span><h3>{title}</h3><p className="muted">{description}</p></div>;
}
