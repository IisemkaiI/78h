/** Authoring calls against `/api/v1/courses`. Every call requires a token. */

import { apiRequest } from './apiClient';
import type {
  CourseDetail,
  CourseModule,
  CoursePage,
  CourseUpdatePayload,
  CourseWritePayload,
  Lesson,
  LessonUpdatePayload,
  LessonWritePayload,
  ModuleWritePayload,
} from '../types/api';

const COURSES_PREFIX = '/api/v1/courses';

function coursePath(courseId: string): string {
  return `${COURSES_PREFIX}/${courseId}`;
}

function modulePath(courseId: string, moduleId: string): string {
  return `${coursePath(courseId)}/modules/${moduleId}`;
}

export function listMyCourses(
  token: string,
  page = 1,
  pageSize = 12,
  signal?: AbortSignal,
): Promise<CoursePage> {
  return apiRequest<CoursePage>(
    `${COURSES_PREFIX}/mine?page=${page}&page_size=${pageSize}`,
    { token, signal },
  );
}

export function createCourse(token: string, payload: CourseWritePayload): Promise<CourseDetail> {
  return apiRequest<CourseDetail>(COURSES_PREFIX, { method: 'POST', body: payload, token });
}

export function getCourse(
  token: string,
  courseId: string,
  signal?: AbortSignal,
): Promise<CourseDetail> {
  return apiRequest<CourseDetail>(coursePath(courseId), { token, signal });
}

export function updateCourse(
  token: string,
  courseId: string,
  payload: CourseUpdatePayload,
): Promise<CourseDetail> {
  return apiRequest<CourseDetail>(coursePath(courseId), {
    method: 'PATCH',
    body: payload,
    token,
  });
}

export function publishCourse(token: string, courseId: string): Promise<CourseDetail> {
  return apiRequest<CourseDetail>(`${coursePath(courseId)}/publish`, {
    method: 'POST',
    token,
  });
}

export function unpublishCourse(token: string, courseId: string): Promise<CourseDetail> {
  return apiRequest<CourseDetail>(`${coursePath(courseId)}/unpublish`, {
    method: 'POST',
    token,
  });
}

export function archiveCourse(token: string, courseId: string): Promise<CourseDetail> {
  return apiRequest<CourseDetail>(`${coursePath(courseId)}/archive`, {
    method: 'POST',
    token,
  });
}

export function deleteCourse(token: string, courseId: string): Promise<null> {
  return apiRequest<null>(coursePath(courseId), { method: 'DELETE', token });
}

/* --- modules ------------------------------------------------------------- */

export function createModule(
  token: string,
  courseId: string,
  payload: ModuleWritePayload,
): Promise<CourseModule> {
  return apiRequest<CourseModule>(`${coursePath(courseId)}/modules`, {
    method: 'POST',
    body: payload,
    token,
  });
}

export function updateModule(
  token: string,
  courseId: string,
  moduleId: string,
  payload: ModuleWritePayload,
): Promise<CourseModule> {
  return apiRequest<CourseModule>(modulePath(courseId, moduleId), {
    method: 'PATCH',
    body: payload,
    token,
  });
}

export function deleteModule(
  token: string,
  courseId: string,
  moduleId: string,
): Promise<null> {
  return apiRequest<null>(modulePath(courseId, moduleId), { method: 'DELETE', token });
}

export function reorderModules(
  token: string,
  courseId: string,
  ids: string[],
): Promise<CourseModule[]> {
  return apiRequest<CourseModule[]>(`${coursePath(courseId)}/modules/order`, {
    method: 'PUT',
    body: { ids },
    token,
  });
}

/* --- lessons ------------------------------------------------------------- */

export function createLesson(
  token: string,
  courseId: string,
  moduleId: string,
  payload: LessonWritePayload,
): Promise<Lesson> {
  return apiRequest<Lesson>(`${modulePath(courseId, moduleId)}/lessons`, {
    method: 'POST',
    body: payload,
    token,
  });
}

export function updateLesson(
  token: string,
  courseId: string,
  moduleId: string,
  lessonId: string,
  payload: LessonUpdatePayload,
): Promise<Lesson> {
  return apiRequest<Lesson>(`${modulePath(courseId, moduleId)}/lessons/${lessonId}`, {
    method: 'PATCH',
    body: payload,
    token,
  });
}

export function deleteLesson(
  token: string,
  courseId: string,
  moduleId: string,
  lessonId: string,
): Promise<null> {
  return apiRequest<null>(`${modulePath(courseId, moduleId)}/lessons/${lessonId}`, {
    method: 'DELETE',
    token,
  });
}

export function reorderLessons(
  token: string,
  courseId: string,
  moduleId: string,
  ids: string[],
): Promise<Lesson[]> {
  return apiRequest<Lesson[]>(`${modulePath(courseId, moduleId)}/lessons/order`, {
    method: 'PUT',
    body: { ids },
    token,
  });
}
