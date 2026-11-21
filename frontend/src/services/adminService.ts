import { apiRequest } from './apiClient';
import type { AdminCourse, AdminOrganization, AdminOverview, AdminUser } from '../types/api';

export function getAdminOverview(token: string): Promise<AdminOverview> {
  return apiRequest('/api/v1/admin/overview', { token });
}

export function listAdminUsers(token: string, q = ''): Promise<{ items: AdminUser[]; total: number; page: number; pages: number }> {
  const query = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
  return apiRequest(`/api/v1/admin/users${query}`, { token });
}

export function setAdminUserActive(token: string, id: string, isActive: boolean): Promise<AdminUser> {
  return apiRequest(`/api/v1/admin/users/${id}`, { method: 'PATCH', token, body: { is_active: isActive } });
}

export function listAdminCourses(token: string, q = ''): Promise<{ items: AdminCourse[]; total: number; page: number; pages: number }> {
  const query = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
  return apiRequest(`/api/v1/admin/courses${query}`, { token });
}

export function archiveAdminCourse(token: string, id: string): Promise<null> {
  return apiRequest(`/api/v1/admin/courses/${id}/archive`, { method: 'POST', token });
}

export function listAdminOrganizations(token: string): Promise<AdminOrganization[]> {
  return apiRequest('/api/v1/admin/organizations', { token });
}
