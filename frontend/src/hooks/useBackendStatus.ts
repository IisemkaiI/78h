/** Backend connectivity state for the start page. */

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '../services/apiClient';
import { getHealth, getInfo, getReady } from '../services/systemService';
import type { BackendStatus, HealthResponse, InfoResponse, ReadyResponse } from '../types/api';

export interface BackendState {
  status: BackendStatus;
  health: HealthResponse | null;
  info: InfoResponse | null;
  ready: ReadyResponse | null;
  error: string | null;
  latencyMs: number | null;
  checkedAt: Date | null;
}

const INITIAL_STATE: BackendState = {
  status: 'checking',
  health: null,
  info: null,
  ready: null,
  error: null,
  latencyMs: null,
  checkedAt: null,
};

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Неизвестная ошибка';
}

export function useBackendStatus(): {
  state: BackendState;
  refresh: () => void;
} {
  const [state, setState] = useState<BackendState>(INITIAL_STATE);
  const inFlight = useRef<AbortController | null>(null);

  const check = useCallback(async (): Promise<void> => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;

    setState((previous) => ({ ...previous, status: 'checking', error: null }));

    const startedAt = performance.now();
    try {
      const [health, info] = await Promise.all([
        getHealth(controller.signal),
        getInfo(controller.signal),
      ]);
      const latencyMs = Math.round(performance.now() - startedAt);

      let ready: ReadyResponse | null = null;
      let readyError: string | null = null;
      try {
        ready = await getReady(controller.signal);
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        readyError = describeError(error);
      }

      setState({
        status: 'online',
        health,
        info,
        ready,
        error: readyError,
        latencyMs,
        checkedAt: new Date(),
      });
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      setState({
        status: 'offline',
        health: null,
        info: null,
        ready: null,
        error: describeError(error),
        latencyMs: null,
        checkedAt: new Date(),
      });
    }
  }, []);

  useEffect(() => {
    void check();
    return () => {
      inFlight.current?.abort();
    };
  }, [check]);

  const refresh = useCallback((): void => {
    void check();
  }, [check]);

  return { state, refresh };
}
