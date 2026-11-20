/** Learning calls against `/api/v1/learning`. Enrollment and progress require a token. */

import { apiRequest } from './apiClient';
import type {
  CourseProgress,
  Enrollment,
  EnrollmentPage,
  EnrollmentStatusResponse,
  LearningCourse,
  LearningHistory,
  LearningLessonContent,
  LessonProgressUpdateResult,
  LessonState,
} from '../types/api';

const LEARNING_PREFIX = '/api/v1/learning';

function enrollmentPath(enrollmentId: string): string {
  return `${LEARNING_PREFIX}/enrollments/${enrollmentId}`;
}

export function enroll(token: string, courseId: string): Promise<Enrollment> {
  return apiRequest<Enrollment>(`${LEARNING_PREFIX}/enrollments`, {
    method: 'POST',
    body: { course_id: courseId },
    token,
  });
}

export function listMyEnrollments(
  token: string,
  page = 1,
  pageSize = 12,
  signal?: AbortSignal,
): Promise<EnrollmentPage> {
  return apiRequest<EnrollmentPage>(
    `${LEARNING_PREFIX}/enrollments/mine?page=${page}&page_size=${pageSize}`,
    { token, signal },
  );
}

export function getEnrollmentStatus(
  token: string,
  courseId: string,
  signal?: AbortSignal,
): Promise<EnrollmentStatusResponse> {
  return apiRequest<EnrollmentStatusResponse>(
    `${LEARNING_PREFIX}/enrollments/by-course/${courseId}`,
    { token, signal },
  );
}

export function getEnrollment(
  token: string,
  enrollmentId: string,
  signal?: AbortSignal,
): Promise<Enrollment> {
  return apiRequest<Enrollment>(enrollmentPath(enrollmentId), { token, signal });
}

export function cancelEnrollment(token: string, enrollmentId: string): Promise<null> {
  return apiRequest<null>(enrollmentPath(enrollmentId), { method: 'DELETE', token });
}

export function startEnrollment(token: string, enrollmentId: string): Promise<Enrollment> {
  return apiRequest<Enrollment>(`${enrollmentPath(enrollmentId)}/start`, {
    method: 'POST',
    token,
  });
}

export function getProgress(
  token: string,
  enrollmentId: string,
  signal?: AbortSignal,
): Promise<CourseProgress> {
  return apiRequest<CourseProgress>(`${enrollmentPath(enrollmentId)}/progress`, {
    token,
    signal,
  });
}

export function getLearningHistory(
  token: string,
  enrollmentId: string,
  signal?: AbortSignal,
): Promise<LearningHistory> {
  return apiRequest<LearningHistory>(`${enrollmentPath(enrollmentId)}/history`, {
    token,
    signal,
  });
}

export function setLessonState(
  token: string,
  enrollmentId: string,
  lessonId: string,
  state: LessonState,
): Promise<LessonProgressUpdateResult> {
  return apiRequest<LessonProgressUpdateResult>(
    `${enrollmentPath(enrollmentId)}/lessons/${lessonId}/progress`,
    { method: 'PUT', body: { state }, token },
  );
}

export function getLearningCourse(
  token: string,
  slug: string,
  signal?: AbortSignal,
): Promise<LearningCourse> {
  return apiRequest<LearningCourse>(
    `${LEARNING_PREFIX}/courses/${encodeURIComponent(slug)}`,
    { token, signal },
  );
}

export function getLearningLesson(
  token: string,
  slug: string,
  lessonId: string,
  signal?: AbortSignal,
): Promise<LearningLessonContent> {
  return apiRequest<LearningLessonContent>(
    `${LEARNING_PREFIX}/courses/${encodeURIComponent(slug)}/lessons/${lessonId}`,
    { token, signal },
  );
}
