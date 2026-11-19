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
