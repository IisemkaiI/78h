/** Authentication and profile calls against `/api/v1`. */

import {
  apiRequest,
} from './apiClient';
import type {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
  UpdateProfilePayload,
  UserProfile,
} from '../types/api';

const AUTH_PREFIX = '/api/v1/auth';
const USERS_PREFIX = '/api/v1/users';

export function registerRequest(payload: RegisterPayload): Promise<TokenResponse> {
  return apiRequest<TokenResponse>(`${AUTH_PREFIX}/register`, {
    method: 'POST',
    body: payload,
  });
}

export function loginRequest(payload: LoginPayload): Promise<TokenResponse> {
  return apiRequest<TokenResponse>(`${AUTH_PREFIX}/login`, {
    method: 'POST',
    body: payload,
  });
}

export function logoutRequest(token: string): Promise<null> {
  return apiRequest<null>(`${AUTH_PREFIX}/logout`, {
    method: 'POST',
    token,
  });
}

export function getCurrentUser(token: string, signal?: AbortSignal): Promise<UserProfile> {
  return apiRequest<UserProfile>(`${AUTH_PREFIX}/me`, { token, signal });
}

export function updateProfileRequest(
  token: string,
  payload: UpdateProfilePayload,
): Promise<UserProfile> {
  return apiRequest<UserProfile>(`${USERS_PREFIX}/me`, {
    method: 'PATCH',
    body: payload,
    token,
  });
}
