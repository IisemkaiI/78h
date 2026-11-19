/**
 * Client-side authentication state.
 *
 * The access token lives in `localStorage` (see `tokenStorage`) so a reload keeps
 * the session until the token expires. On start-up the token is validated with
 * `GET /auth/me`; an invalid or expired token is discarded silently.
 *
 * This state is a UX convenience only: every protected operation is authorised
 * by the backend, never by this provider.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ApiError } from '../services/apiClient';
import {
  getCurrentUser,
  loginRequest,
  logoutRequest,
  registerRequest,
  updateProfileRequest,
} from '../services/authService';
import { clearSession, loadSession, saveSession } from '../services/tokenStorage';
import type { RegisterPayload, TokenResponse, UserProfile } from '../types/api';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthState {
  status: AuthStatus;
  token: string | null;
  user: UserProfile | null;
}

export interface AuthContextValue extends AuthState {
  signIn: (result: TokenResponse) => void;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUp: (payload: RegisterPayload) => Promise<void>;
  signOut: () => void;
  updateDisplayName: (displayName: string) => Promise<UserProfile>;
}

const ANONYMOUS: AuthState = { status: 'anonymous', token: null, user: null };

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading', token: null, user: null });

  useEffect(() => {
    const stored = loadSession();
    if (stored === null) {
      setState(ANONYMOUS);
      return;
    }

    const controller = new AbortController();
    let active = true;

    void (async () => {
      try {
        const user = await getCurrentUser(stored.accessToken, controller.signal);
        if (!active) {
          return;
        }
        setState({ status: 'authenticated', token: stored.accessToken, user });
      } catch {
        if (!active) {
          return;
        }
        clearSession();
        setState(ANONYMOUS);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  const signIn = useCallback((result: TokenResponse): void => {
    saveSession(result.access_token, result.expires_in);
    setState({ status: 'authenticated', token: result.access_token, user: result.user });
  }, []);

  const signInWithPassword = useCallback(
    async (email: string, password: string): Promise<void> => {
      signIn(await loginRequest({ email, password }));
    },
    [signIn],
  );

  const signUp = useCallback(
    async (payload: RegisterPayload): Promise<void> => {
      signIn(await registerRequest(payload));
    },
    [signIn],
  );

  const signOut = useCallback((): void => {
    const token = state.token;
    clearSession();
    setState(ANONYMOUS);
    if (token !== null) {
      // Best effort: the request is stateless and the local session is already gone.
      void logoutRequest(token).catch(() => undefined);
    }
  }, [state.token]);

  const updateDisplayName = useCallback(
    async (displayName: string): Promise<UserProfile> => {
      const token = state.token;
      if (token === null) {
        throw new ApiError('http', 'Требуется авторизация.', 401, 'not_authenticated');
      }
      const user = await updateProfileRequest(token, { display_name: displayName });
      setState((previous) => ({ ...previous, user }));
      return user;
    },
    [state.token],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      signIn,
      signInWithPassword,
      signUp,
      signOut,
      updateDisplayName,
    }),
    [state, signIn, signInWithPassword, signUp, signOut, updateDisplayName],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth() must be used inside <AuthProvider>');
  }
  return context;
}
