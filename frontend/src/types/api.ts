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

/* --- Sprint 8: organizations and corporate learning --------------------- */

export type OrganizationRole = 'owner' | 'admin' | 'manager' | 'employee';
export type InvitationRole = 'admin' | 'manager' | 'employee';
export type InvitationStatus = 'pending' | 'accepted' | 'revoked' | 'expired';
export type CorporateAssignmentStatus = 'pending' | 'accepted' | 'declined' | 'cancelled';

export interface Organization {
  id: string;
  name: string;
  slug: string;
  status: 'active' | 'suspended' | 'archived';
  created_by_id: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface OrganizationMembership {
  id: string;
  user_id: string;
  display_name: string;
  email: string;
  role: OrganizationRole;
  status: 'active' | 'suspended' | 'removed';
  joined_at: string | null;
  created_at: string;
  can_update_role: boolean;
  can_remove: boolean;
  department_id: string | null;
}

export interface OrganizationDepartment {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  members_count: number;
}

export interface AdminOverview {
  users_total: number;
  organizations_total: number;
  courses_total: number;
  assignments_total: number;
  assignments_pending: number;
  assignments_accepted: number;
  completed_courses: number;
  average_progress_percent: number;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  roles: string[];
  created_at: string;
}

export interface AdminCourse {
  id: string;
  title: string;
  slug: string;
  status: string;
  author_name: string;
  created_at: string;
}

export interface AdminOrganization {
  id: string;
  name: string;
  slug: string;
  status: string;
  members_count: number;
  created_at: string;
}

export interface OrganizationInvitation {
  id: string;
  email: string;
  role: InvitationRole;
  status: InvitationStatus;
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  token?: string;
}

export interface CorporateAssignment {
  id: string;
  organization_id: string;
  membership_id: string;
  learner_user_id: string;
  learner_name: string;
  department_id: string | null;
  course_id: string;
  course_title: string;
  enrollment_id: string | null;
  enrollment_status: EnrollmentStatus | null;
  progress_percent: number | null;
  is_course_completed: boolean | null;
  status: CorporateAssignmentStatus;
  is_required: boolean;
  due_at: string | null;
  assigned_at: string;
  accepted_at: string | null;
  declined_at: string | null;
  cancelled_at: string | null;
  overdue_at: string | null;
}

export interface CorporateAssignmentPage {
  items: CorporateAssignment[];
  total: number;
}

export interface OrganizationLearningStats {
  assignments_total: number;
  pending: number;
  accepted: number;
  declined: number;
  cancelled: number;
  learners_total: number;
  active_enrollments: number;
  completed_enrollments: number;
  average_progress_percent: number;
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

/* --- Sprint 4: learning process ----------------------------------------- */

export type EnrollmentStatus = 'active' | 'cancelled';
export type LessonState = 'not_started' | 'in_progress' | 'completed';

export interface EnrollmentCourse {
  id: string;
  title: string;
  slug: string;
  short_description: string;
  cover_image_url: string | null;
  level: CourseLevel;
  language: string;
  category_name: string;
  author_display_name: string;
}

export interface CourseProgress {
  total_lessons: number;
  completed_lessons: number;
  in_progress_lessons: number;
  not_started_lessons: number;
  progress_percent: number;
  is_completed: boolean;
  total_required_assessments: number;
  completed_required_assessments: number;
  completed_at: string | null;
  removed_lessons_count: number;
}

export interface Enrollment {
  id: string;
  user_id: string;
  course_id: string;
  status: EnrollmentStatus;
  enrolled_at: string;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
  course: EnrollmentCourse;
  progress: CourseProgress;
}

export type EnrollmentPage = Paginated<Enrollment>;

export interface EnrollmentStatusResponse {
  enrolled: boolean;
  enrollment: Enrollment | null;
}

export interface LessonProgressEntry {
  lesson_id: string;
  state: LessonState;
  started_at: string | null;
  completed_at: string | null;
  last_viewed_at: string | null;
}

export interface LessonProgressUpdateResult {
  lesson: LessonProgressEntry;
  course_progress: CourseProgress;
}

export interface LearningEvent {
  id: string;
  event_type: string;
  lesson_id: string | null;
  lesson_id_original: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RemovedLesson {
  lesson_id_original: string;
  module_id_original: string;
  lesson_title: string;
  module_title: string;
  state: LessonState;
  started_at: string | null;
  completed_at: string | null;
}

export interface LearningHistory {
  events: LearningEvent[];
  removed_lessons: RemovedLesson[];
}

export interface LearningCourseInfo {
  id: string;
  title: string;
  slug: string;
  status: CourseStatus;
  cover_image_url: string | null;
  level: CourseLevel;
  category_name: string;
}

export interface LearningLesson {
  id: string;
  module_id: string;
  title: string;
  description: string | null;
  position: number;
  estimated_duration_minutes: number;
  state: LessonState;
  started_at: string | null;
  completed_at: string | null;
  quizzes: LearningQuiz[];
  assignments: LearningAssignment[];
}

export interface LearningQuiz {
  id: string;
  title: string;
  description: string | null;
  is_required: boolean;
  passing_score_percent: number;
  time_limit_minutes: number | null;
  max_attempts: number | null;
}

export interface LearningAssignment {
  id: string;
  title: string;
  description: string;
  requirements: string | null;
  max_points: number;
  due_at: string | null;
  is_required: boolean;
  allow_resubmission: boolean;
}

export interface LearningLessonContent extends LearningLesson {
  content: string;
}

export interface LearningModule {
  id: string;
  title: string;
  description: string | null;
  position: number;
  lessons: LearningLesson[];
}

export interface LearningCourse {
  enrollment_id: string | null;
  course: LearningCourseInfo;
  progress: CourseProgress;
  modules: LearningModule[];
}
