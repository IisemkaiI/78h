/**
 * Minimal fetch wrapper for the Education Platform API.
 *
 * Responsibilities:
 *  - resolve the backend base URL from the environment;
 *  - apply a request timeout;
 *  - serialise JSON bodies and attach a bearer token when asked;
 *  - normalise failures into `ApiError` (network, timeout, HTTP, bad payload).
 */

import type { ApiErrorResponse } from '../types/api';

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';
const DEFAULT_TIMEOUT_MS = 8_000;
const REQUEST_TIMEOUT_REASON = 'request-timeout';

export const API_BASE_URL: string = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL
).replace(/\/+$/, '');

export type ApiErrorKind = 'network' | 'timeout' | 'http' | 'invalid_response';

export class ApiError extends Error {
  override readonly name = 'ApiError';
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string;
  readonly details: unknown;

  constructor(
    kind: ApiErrorKind,
    message: string,
    status: number | null = null,
    code = 'error',
    details: unknown = null,
  ) {
    super(message);
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** True when the backend could not be reached at all. */
  get isConnectivityProblem(): boolean {
    return this.kind === 'network' || this.kind === 'timeout';
  }
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface RequestOptions {
  method?: HttpMethod;
  /** JSON-serialisable request body. */
  body?: unknown;
  /** Bearer token for authenticated endpoints. */
  token?: string | null;
  timeoutMs?: number;
  signal?: AbortSignal;
  /** Status codes whose body should be returned instead of throwing (e.g. 503). */
  acceptedStatusCodes?: readonly number[];
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false;
  }
  const { error } = value;
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    'message' in error &&
    typeof error.code === 'string' &&
    typeof error.message === 'string'
  );
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = 'GET',
    body,
    token,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal,
    acceptedStatusCodes = [],
  } = options;

  const controller = new AbortController();
  const cancelOnExternalAbort = (): void => controller.abort(signal?.reason);

  if (signal) {
    if (signal.aborted) {
      controller.abort(signal.reason);
    } else {
      signal.addEventListener('abort', cancelOnExternalAbort, { once: true });
    }
  }

  const timeoutId = window.setTimeout(() => controller.abort(REQUEST_TIMEOUT_REASON), timeoutMs);

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (error) {
      if (controller.signal.reason === REQUEST_TIMEOUT_REASON) {
        throw new ApiError(
          'timeout',
          `Backend не ответил за ${Math.round(timeoutMs / 1000)} с.`,
        );
      }
      if (signal?.aborted) {
        throw error;
      }
      throw new ApiError('network', 'Не удалось подключиться к backend. Проверьте, запущен ли сервер.');
    }

    let payload: unknown = null;
    const rawBody = await response.text();
    if (rawBody.length > 0) {
      try {
        payload = JSON.parse(rawBody) as unknown;
      } catch {
        throw new ApiError(
          'invalid_response',
          'Backend вернул ответ, который не является корректным JSON.',
          response.status,
          'invalid_response',
        );
      }
    }

    if (!response.ok && !acceptedStatusCodes.includes(response.status)) {
      if (isApiErrorResponse(payload)) {
        throw new ApiError(
          'http',
          payload.error.message,
          response.status,
          payload.error.code,
          payload.error.details,
        );
      }
      throw new ApiError(
        'http',
        `Backend ответил со статусом ${response.status}.`,
        response.status,
        'http_error',
      );
    }

    return payload as T;
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener('abort', cancelOnExternalAbort);
  }
}
