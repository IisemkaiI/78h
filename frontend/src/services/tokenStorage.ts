/**
 * Persistence of the access token in `localStorage`.
 *
 * The server never receives the token from storage: it is attached as an
 * `Authorization` header on each request. The expiry timestamp returned by the
 * API is stored alongside it so an obviously stale session is discarded on
 * start-up without an extra request.
 */

const STORAGE_KEY = 'education-platform.auth.v1';

export interface StoredSession {
  accessToken: string;
  expiresAt: number;
}

function isStoredSession(value: unknown): value is StoredSession {
  return (
    typeof value === 'object' &&
    value !== null &&
    'accessToken' in value &&
    'expiresAt' in value &&
    typeof value.accessToken === 'string' &&
    typeof value.expiresAt === 'number'
  );
}

export function loadSession(): StoredSession | null {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (raw === null) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isStoredSession(parsed) || parsed.accessToken.length === 0) {
      clearSession();
      return null;
    }
    if (parsed.expiresAt <= Date.now()) {
      clearSession();
      return null;
    }
    return parsed;
  } catch {
    clearSession();
    return null;
  }
}

export function saveSession(accessToken: string, expiresInSeconds: number): StoredSession {
  const session: StoredSession = {
    accessToken,
    expiresAt: Date.now() + expiresInSeconds * 1000,
  };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Storage can be unavailable (private mode); the in-memory session still works.
  }
  return session;
}

export function clearSession(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clean up.
  }
}
