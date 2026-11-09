/**
 * Typed HTTP client for the PowerShift backend.
 * Every request carries the per-launch token; every error becomes an ApiError
 * with the backend's { error: { code, message, fields } } shape.
 */
import type { BackendConnection } from '@/api/connection';

export const TOKEN_HEADER = 'X-PowerShift-Token';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;

  constructor(status: number, code: string, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

/** Field-level messages from a failed request, keyed by API field path. */
export function fieldErrorsOf(error: unknown): Record<string, string> {
  return error instanceof ApiError ? error.fields : {};
}

interface ErrorBody {
  error?: { code?: string; message?: string; fields?: Record<string, string> };
}

export interface ApiClient {
  get<T>(path: string): Promise<T>;
  send<T>(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<T>;
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {};
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    // Non-JSON error (should not happen with our backend); fall through to defaults.
  }
  return new ApiError(
    response.status,
    body.error?.code ?? 'http_error',
    body.error?.message ?? `Request failed with status ${response.status}`,
    body.error?.fields ?? {},
  );
}

export function createApiClient(connection: BackendConnection, fetchImpl: typeof fetch = fetch): ApiClient {
  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    if (connection.token) headers[TOKEN_HEADER] = connection.token;
    if (body !== undefined) headers['Content-Type'] = 'application/json';

    let response: Response;
    try {
      response = await fetchImpl(`${connection.baseUrl}${path}`, {
        method,
        headers,
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    } catch {
      throw new ApiError(0, 'backend_unreachable', 'The PowerShift backend is not responding.');
    }

    if (!response.ok) throw await toApiError(response);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  return {
    get: (path) => request('GET', path),
    send: (method, path, body) => request(method, path, body),
  };
}
