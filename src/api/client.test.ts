import { describe, expect, it, vi } from 'vitest';
import { ApiError, createApiClient, TOKEN_HEADER } from '@/api/client';
import { jsonResponse, TEST_CONNECTION } from '@/test/render';

describe('createApiClient', () => {
  it('sends the per-launch token and returns parsed JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' }));
    const client = createApiClient(TEST_CONNECTION, fetchMock);

    const result = await client.get<{ status: string }>('/api/health');

    expect(result).toEqual({ status: 'ok' });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://backend.test/api/health');
    expect((init.headers as Record<string, string>)[TOKEN_HEADER]).toBe('test-token');
  });

  it('omits the token header when there is no token (browser dev mode)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    const client = createApiClient({ baseUrl: 'http://x', token: null }, fetchMock);

    await client.get('/api/health');

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers).not.toHaveProperty(TOKEN_HEADER);
  });

  it('serialises a JSON body for POST requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }, 201));
    const client = createApiClient(TEST_CONNECTION, fetchMock);

    await client.send('POST', '/api/things', { name: 'Fridge' });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"name":"Fridge"}');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('turns backend error bodies into ApiError with field details', async () => {
    const body = { error: { code: 'validation_error', message: 'Some values are invalid.', fields: { name: 'Required' } } };
    const client = createApiClient(TEST_CONNECTION, vi.fn().mockResolvedValue(jsonResponse(body, 422)));

    const error = await client.get('/api/x').catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: 'validation_error', fields: { name: 'Required' } });
  });

  it('reports an unreachable backend clearly when fetch itself fails', async () => {
    const client = createApiClient(TEST_CONNECTION, vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(client.get('/api/health')).rejects.toMatchObject({ status: 0, code: 'backend_unreachable' });
  });
});
