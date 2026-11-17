/** Typed calls to the backend service endpoints. */

import { apiRequest } from './apiClient';
import type { HealthResponse, InfoResponse, ReadyResponse } from '../types/api';

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/api/v1/health', { signal, timeoutMs: 5_000 });
}

export function getInfo(signal?: AbortSignal): Promise<InfoResponse> {
  return apiRequest<InfoResponse>('/api/v1/info', { signal, timeoutMs: 5_000 });
}

/**
 * Readiness always returns a body: 200 when the database is reachable,
 * 503 with `status: "not_ready"` otherwise. Both are accepted here so the UI
 * can show *why* the backend is not ready.
 */
export function getReady(signal?: AbortSignal): Promise<ReadyResponse> {
  return apiRequest<ReadyResponse>('/api/v1/ready', {
    signal,
    timeoutMs: 8_000,
    acceptedStatusCodes: [503],
  });
}
