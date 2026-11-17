/**
 * Minimal fetch wrapper for the Education Platform API.
 *
 * Responsibilities:
 *  - resolve the backend base URL from the environment;
 *  - apply a request timeout;
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

  constructor(kind: ApiErrorKind, message: string, status: number | null = null, code = 'error') {
    super(message);
    this.kind = kind;
    this.status = status;
    this.code = code;
  }

  /** True when the backend could not be reached at all. */
  get isConnectivityProblem(): boolean {
    return this.kind === 'network' || this.kind === 'timeout';
  }
}

export interface RequestOptions {
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
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal, acceptedStatusCodes = [] } = options;

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

  try {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
    } catch (error) {
      if (controller.signal.reason === REQUEST_TIMEOUT_REASON) {
        throw new ApiError(
          'timeout',
          `Backend did not respond within ${Math.round(timeoutMs / 1000)} s.`,
        );
      }
      if (signal?.aborted) {
        throw error;
      }
      throw new ApiError('network', 'Could not reach the backend. Is it running?');
    }

    let payload: unknown = null;
    const rawBody = await response.text();
    if (rawBody.length > 0) {
      try {
        payload = JSON.parse(rawBody) as unknown;
      } catch {
        throw new ApiError(
          'invalid_response',
          'Backend returned a response that is not valid JSON.',
          response.status,
          'invalid_response',
        );
      }
    }

    if (!response.ok && !acceptedStatusCodes.includes(response.status)) {
      if (isApiErrorResponse(payload)) {
        throw new ApiError('http', payload.error.message, response.status, payload.error.code);
      }
      throw new ApiError(
        'http',
        `Backend responded with status ${response.status}.`,
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
