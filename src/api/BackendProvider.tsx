import { createContext, use, useEffect, useMemo, useState, type ReactNode } from 'react';
import { createApiClient, type ApiClient } from '@/api/client';
import { waitForBackend, type BackendConnection } from '@/api/connection';
import { StartupScreen } from '@/app/StartupScreen';

const ApiClientContext = createContext<ApiClient | null>(null);

type ConnectState =
  | { phase: 'connecting' }
  | { phase: 'connected'; connection: BackendConnection }
  | { phase: 'failed'; message: string };

interface BackendProviderProps {
  children: ReactNode;
  /** Injected in tests; defaults to the real Tauri/browser discovery. */
  connect?: (signal: AbortSignal) => Promise<BackendConnection>;
}

/** Blocks the UI behind a startup screen until the local backend is reachable. */
export function BackendProvider({ children, connect = waitForBackend }: BackendProviderProps) {
  const [state, setState] = useState<ConnectState>({ phase: 'connecting' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    connect(controller.signal)
      .then((connection) => setState({ phase: 'connected', connection }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({ phase: 'failed', message: error instanceof Error ? error.message : String(error) });
      });
    return () => controller.abort();
  }, [connect, attempt]);

  const client = useMemo(
    () => (state.phase === 'connected' ? createApiClient(state.connection) : null),
    [state],
  );

  if (state.phase !== 'connected' || client === null) {
    return (
      <StartupScreen
        error={state.phase === 'failed' ? state.message : null}
        onRetry={() => {
          setState({ phase: 'connecting' });
          setAttempt((n) => n + 1);
        }}
      />
    );
  }

  return <ApiClientContext value={client}>{children}</ApiClientContext>;
}

export function useApiClient(): ApiClient {
  const client = use(ApiClientContext);
  if (!client) throw new Error('useApiClient must be used inside <BackendProvider>');
  return client;
}
