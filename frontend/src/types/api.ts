/**
 * Contract between the frontend and the FastAPI backend (API v1).
 * Mirrors `backend/app/api/v1/schemas.py`.
 */

export interface HealthResponse {
  status: 'ok';
  service: string;
  version: string;
  environment: string;
}

export interface DatabaseStatus {
  status: 'available' | 'unavailable';
  detail: string | null;
  latency_ms: number | null;
}

export interface ReadyResponse {
  status: 'ready' | 'not_ready';
  version: string;
  database: DatabaseStatus;
}

export interface InfoResponse {
  application: string;
  version: string;
  environment: string;
  api_version: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details: unknown;
}

export interface ApiErrorResponse {
  error: ApiErrorBody;
}

/** Result of a full backend connectivity check shown on the start page. */
export type BackendStatus = 'checking' | 'online' | 'offline';

/* --- Sprint 1: users, authentication and RBAC ---------------------------- */

export interface UserRole {
  code: string;
  name: string;
}

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  roles: UserRole[];
  permissions: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: UserProfile;
}

export interface RegisterPayload {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UpdateProfilePayload {
  display_name: string;
}

/* --- Sprint 2: catalog, courses and structure ---------------------------- */

export type CourseLevel = 'beginner' | 'intermediate' | 'advanced';
export type CourseStatus = 'draft' | 'published' | 'archived';
export type CatalogSort = 'newest' | 'oldest' | 'title';

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CategoryBrief {
  id: string;
  name: string;
  slug: string;
}

export interface AuthorBrief {
  id: string;
  display_name: string;
}

export interface Lesson {
  id: string;
  module_id: string;
  title: string;
  description: string | null;
  content: string;
  position: number;
  estimated_duration_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface LessonPreview {
  id: string;
  title: string;
  description: string | null;
  position: number;
  estimated_duration_minutes: number;
}

export interface CourseModule {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  position: number;
  lessons: Lesson[];
  created_at: string;
  updated_at: string;
}

export interface ModulePreview {
  id: string;
  title: string;
  description: string | null;
  position: number;
  lessons: LessonPreview[];
}

export interface CourseSummary {
  id: string;
  title: string;
  slug: string;
  short_description: string;
  cover_image_url: string | null;
  level: CourseLevel;
  language: string;
  status: CourseStatus;
  author_id: string;
  category: CategoryBrief;
  author: AuthorBrief;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  modules_count: number;
  lessons_count: number;
  total_duration_minutes: number;
}

export interface CourseDetail extends CourseSummary {
  description: string;
  modules: CourseModule[];
}

export interface CatalogCourse {
  id: string;
  title: string;
  slug: string;
  short_description: string;
  cover_image_url: string | null;
  level: CourseLevel;
  language: string;
  category: CategoryBrief;
  author: AuthorBrief;
  published_at: string | null;
  modules_count: number;
  lessons_count: number;
  total_duration_minutes: number;
}

export interface CatalogCourseDetail extends CatalogCourse {
  description: string;
  modules: ModulePreview[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type CatalogPage = Paginated<CatalogCourse>;
export type CoursePage = Paginated<CourseSummary>;

export interface CourseWritePayload {
  title: string;
  short_description: string;
  description: string;
  cover_image_url: string | null;
  level: CourseLevel;
  language: string;
  category_id: string;
}

/** PATCH payload: only supplied keys are sent. */
export type CourseUpdatePayload = Partial<CourseWritePayload>;

export interface ModuleWritePayload {
  title: string;
  description: string | null;
}

export interface LessonWritePayload {
  title: string;
  description: string | null;
  content: string;
  estimated_duration_minutes: number;
}

export type LessonUpdatePayload = Partial<LessonWritePayload>;
