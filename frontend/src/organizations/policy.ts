import type { InvitationRole, OrganizationMembership, OrganizationRole } from '../types/api';

export type CabinetRole = OrganizationRole | 'platform_admin' | null;

export function canManageMember(
  actorRole: CabinetRole,
  target: Pick<OrganizationMembership, 'user_id' | 'role'> & Partial<Pick<OrganizationMembership, 'can_remove' | 'can_update_role'>>,
  actorUserId: string | undefined,
  activeOwnerCount: number,
): boolean {
  if (typeof target.can_remove === 'boolean' && typeof target.can_update_role === 'boolean') {
    return target.can_remove || target.can_update_role;
  }
  if (target.user_id === actorUserId) return false;
  if (target.role === 'owner' && activeOwnerCount <= 1) return false;
  if (actorRole === 'owner') return true;
  if (actorRole === 'admin') return target.role === 'manager' || target.role === 'employee';
  return actorRole === 'manager' && target.role === 'employee';
}

export function editableMemberRoles(
  actorRole: CabinetRole,
  targetRole: OrganizationRole,
  activeOwnerCount: number,
): OrganizationRole[] {
  if (actorRole === 'owner') {
    if (targetRole === 'owner' && activeOwnerCount <= 1) return [];
    return ['owner', 'admin', 'manager', 'employee'];
  }
  if (actorRole === 'admin' && (targetRole === 'employee' || targetRole === 'manager')) {
    return ['employee', 'manager'];
  }
  return [];
}

export function invitationRoles(actorRole: CabinetRole): InvitationRole[] {
  if (actorRole === 'owner') return ['admin', 'manager', 'employee'];
  if (actorRole === 'admin') return ['manager', 'employee'];
  if (actorRole === 'manager') return ['employee'];
  return [];
}

export function canRevokeInvitation(
  actorRole: CabinetRole,
  invitationRole: InvitationRole,
  status: string,
): boolean {
  if (status !== 'pending') return false;
  if (actorRole === 'owner') return true;
  if (actorRole === 'admin') return invitationRole !== 'admin';
  return actorRole === 'manager' && invitationRole === 'employee';
}

export function canLeaveOrganization(actorRole: CabinetRole, activeOwnerCount: number): boolean {
  if (actorRole === null || actorRole === 'platform_admin') return false;
  return actorRole !== 'owner' || activeOwnerCount > 1;
}
