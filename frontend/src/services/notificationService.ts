import { apiRequest } from './apiClient';

export interface NotificationItem {
  id: string;
  type: 'course_completed' | 'quiz_completed' | 'assignment_accepted' | 'assignment_revision_required' | 'certificate_issued';
  title: string;
  body: string;
  payload: Record<string, string | number | boolean>;
  created_at: string;
  read_at: string | null;
}

export interface NotificationPage {
  items: NotificationItem[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export const getNotifications = (token: string, page = 1) =>
  apiRequest<NotificationPage>(`/api/v1/notifications/me?page=${page}&page_size=20`, { token });

export const getUnreadCount = (token: string) =>
  apiRequest<{ unread_count: number }>('/api/v1/notifications/unread-count', { token });

export const markNotificationRead = (token: string, id: string) =>
  apiRequest<NotificationItem>(`/api/v1/notifications/${id}/read`, { method: 'PATCH', token });

export const markAllNotificationsRead = (token: string) =>
  apiRequest<{ updated: number }>('/api/v1/notifications/read-all', { method: 'POST', token });
