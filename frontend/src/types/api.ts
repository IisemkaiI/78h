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
