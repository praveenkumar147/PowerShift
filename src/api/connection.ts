/**
 * Finding the local backend.
 *
 * Inside the desktop app, the Rust shell starts the Python backend and knows its
 * port and the per-launch token; we ask it through the `backend_status` command.
 * In a plain browser (`npm run dev` without Tauri) we use a backend you started by
 * hand at VITE_API_URL (default http://127.0.0.1:8000), with no token.
 */
import { invoke, isTauri } from '@tauri-apps/api/core';

export interface BackendConnection {
  baseUrl: string;
  token: string | null;
}

/** Mirrors the BackendStatus enum in src-tauri/src/backend.rs. */
export type BackendStatus =
  | { state: 'starting' }
  | { state: 'ready'; port: number; token: string }
  | { state: 'failed'; message: string };

const DEFAULT_BROWSER_DEV_URL = 'http://127.0.0.1:8000';
const POLL_INTERVAL_MS = 250;

function browserDevConnection(): BackendConnection {
  const url = import.meta.env.VITE_API_URL as string | undefined;
  return { baseUrl: url ?? DEFAULT_BROWSER_DEV_URL, token: null };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Resolves once the backend is ready; rejects if the desktop shell reports a failure. */
export async function waitForBackend(signal: AbortSignal): Promise<BackendConnection> {
  if (!isTauri()) return browserDevConnection();

  while (!signal.aborted) {
    const status = await invoke<BackendStatus>('backend_status');
    if (status.state === 'ready') {
      return { baseUrl: `http://127.0.0.1:${status.port}`, token: status.token };
    }
    if (status.state === 'failed') throw new Error(status.message);
    await sleep(POLL_INTERVAL_MS);
  }
  throw new DOMException('Backend wait was cancelled', 'AbortError');
}
