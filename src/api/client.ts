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

export interface DownloadedFile {
  blob: Blob;
  /** From the Content-Disposition header, or the fallback given by the caller. */
  filename: string;
}

export interface ApiClient {
  get<T>(path: string): Promise<T>;
  send<T>(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<T>;
  /** POST (or GET, when `body` is omitted) a request whose answer is a file. */
  download(path: string, body: unknown | undefined, fallbackName: string): Promise<DownloadedFile>;
  /** POST a file as the raw request body (used to restore a backup). */
  upload<T>(path: string, file: Blob): Promise<T>;
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

/** "attachment; filename="report.csv"" -> "report.csv" */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  const match = header ? /filename="?([^";]+)"?/i.exec(header) : null;
  return match?.[1] ?? fallback;
}

export function createApiClient(connection: BackendConnection, fetchImpl: typeof fetch = fetch): ApiClient {
  async function perform(method: string, path: string, init: { body?: BodyInit; contentType?: string } = {}): Promise<Response> {
    const headers: Record<string, string> = {};
    if (connection.token) headers[TOKEN_HEADER] = connection.token;
    if (init.contentType) headers['Content-Type'] = init.contentType;

    let response: Response;
    try {
      response = await fetchImpl(`${connection.baseUrl}${path}`, {
        method,
        headers,
        ...(init.body !== undefined ? { body: init.body } : {}),
      });
    } catch {
      throw new ApiError(0, 'backend_unreachable', 'The PowerShift backend is not responding.');
    }
    if (!response.ok) throw await toApiError(response);
    return response;
  }

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const response = await perform(method, path, body === undefined ? {} : { body: JSON.stringify(body), contentType: 'application/json' });
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  return {
    get: (path) => request('GET', path),
    send: (method, path, body) => request(method, path, body),
    async download(path, body, fallbackName) {
      const response =
        body === undefined
          ? await perform('GET', path)
          : await perform('POST', path, { body: JSON.stringify(body), contentType: 'application/json' });
      return {
        blob: await response.blob(),
        filename: filenameFromDisposition(response.headers.get('Content-Disposition'), fallbackName),
      };
    },
    async upload<T>(path: string, file: Blob) {
      const response = await perform('POST', path, { body: file, contentType: 'application/octet-stream' });
      return (await response.json()) as T;
    },
  };
}
