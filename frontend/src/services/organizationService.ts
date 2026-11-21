import { apiRequest } from './apiClient';
import type {
  CorporateAssignment,
  CorporateAssignmentPage,
  InvitationRole,
  Organization,
  OrganizationInvitation,
  OrganizationLearningStats,
  OrganizationDepartment,
  OrganizationMembership,
  OrganizationRole,
} from '../types/api';

const PREFIX = '/api/v1/organizations';

export function listOrganizationDepartments(token: string, organizationId: string): Promise<OrganizationDepartment[]> {
  return apiRequest(`${PREFIX}/${organizationId}/departments`, { token });
}

export function createOrganizationDepartment(token: string, organizationId: string, name: string): Promise<OrganizationDepartment> {
  return apiRequest(`${PREFIX}/${organizationId}/departments`, { method: 'POST', token, body: { name } });
}

export function renameOrganizationDepartment(token: string, organizationId: string, departmentId: string, name: string): Promise<OrganizationDepartment> {
  return apiRequest(`${PREFIX}/${organizationId}/departments/${departmentId}`, { method: 'PATCH', token, body: { name } });
}

export function deleteOrganizationDepartment(token: string, organizationId: string, departmentId: string): Promise<null> {
  return apiRequest(`${PREFIX}/${organizationId}/departments/${departmentId}`, { method: 'DELETE', token });
}

export function setMemberDepartment(token: string, organizationId: string, membershipId: string, departmentId: string | null): Promise<OrganizationMembership> {
  return apiRequest(`${PREFIX}/${organizationId}/members/${membershipId}/department`, { method: 'PATCH', token, body: { department_id: departmentId } });
}

export function listMyOrganizations(token: string): Promise<{ items: Organization[] }> {
  return apiRequest(`${PREFIX}/me`, { token });
}

export function createOrganization(token: string, name: string, slug: string): Promise<Organization> {
  return apiRequest(`${PREFIX}`, { method: 'POST', body: { name, slug }, token });
}

export function getOrganization(token: string, organizationId: string): Promise<Organization> {
  return apiRequest(`${PREFIX}/${organizationId}`, { token });
}

export function listOrganizationMembers(token: string, organizationId: string): Promise<OrganizationMembership[]> {
  return apiRequest(`${PREFIX}/${organizationId}/members`, { token });
}

export function updateMemberRole(
  token: string,
  organizationId: string,
  membershipId: string,
  role: OrganizationRole,
): Promise<OrganizationMembership> {
  return apiRequest(`${PREFIX}/${organizationId}/members/${membershipId}`, {
    method: 'PATCH', body: { role }, token,
  });
}

export function removeOrganizationMember(token: string, organizationId: string, membershipId: string): Promise<null> {
  return apiRequest(`${PREFIX}/${organizationId}/members/${membershipId}`, { method: 'DELETE', token });
}

export function leaveOrganization(token: string, organizationId: string): Promise<null> {
  return apiRequest(`${PREFIX}/${organizationId}/leave`, { method: 'POST', token });
}

export function listInvitations(token: string, organizationId: string): Promise<{ items: OrganizationInvitation[] }> {
  return apiRequest(`${PREFIX}/${organizationId}/invitations`, { token });
}

export function createInvitation(
  token: string,
  organizationId: string,
  email: string,
  role: InvitationRole,
): Promise<OrganizationInvitation> {
  return apiRequest(`${PREFIX}/${organizationId}/invitations`, {
    method: 'POST', body: { email, role }, token,
  });
}

export function revokeInvitation(token: string, organizationId: string, invitationId: string): Promise<null> {
  return apiRequest(`${PREFIX}/${organizationId}/invitations/${invitationId}`, { method: 'DELETE', token });
}

export function acceptOrganizationInvitation(authToken: string, invitationToken: string): Promise<{
  invitation_id: string;
  organization_id: string;
  membership_id: string;
  role: OrganizationRole;
  joined_at: string;
}> {
  return apiRequest(`${PREFIX}/invitations/accept`, { method: 'POST', body: { token: invitationToken }, token: authToken });
}

export function listCorporateAssignments(token: string, organizationId: string): Promise<CorporateAssignmentPage> {
  return apiRequest(`${PREFIX}/${organizationId}/assignments`, { token });
}

export function createCorporateAssignments(
  token: string,
  organizationId: string,
  courseId: string,
  membershipIds: string[],
  dueAt: string | null,
  isRequired: boolean,
): Promise<CorporateAssignment[]> {
  return apiRequest(`${PREFIX}/${organizationId}/assignments`, {
    method: 'POST',
    body: { course_id: courseId, membership_ids: membershipIds, due_at: dueAt, is_required: isRequired },
    token,
  });
}

export function acceptCorporateAssignment(token: string, organizationId: string, assignmentId: string): Promise<CorporateAssignment> {
  return apiRequest(`${PREFIX}/${organizationId}/assignments/${assignmentId}/accept`, { method: 'POST', token });
}

export function declineCorporateAssignment(token: string, organizationId: string, assignmentId: string): Promise<CorporateAssignment> {
  return apiRequest(`${PREFIX}/${organizationId}/assignments/${assignmentId}/decline`, { method: 'POST', token });
}

export function cancelCorporateAssignment(token: string, organizationId: string, assignmentId: string): Promise<null> {
  return apiRequest(`${PREFIX}/${organizationId}/assignments/${assignmentId}`, { method: 'DELETE', token });
}

export function getOrganizationLearningStats(token: string, organizationId: string): Promise<OrganizationLearningStats> {
  return apiRequest(`${PREFIX}/${organizationId}/learning-stats`, { token });
}
