import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const preferenceWrites = (requests: Array<{ method: string; path: string; body: unknown }>) =>
  requests.filter((r) => r.method === 'PUT' && r.path === '/api/settings/preferences');

describe('Theme stored in the database', () => {
  it('adopts the theme saved in the database, even if the browser remembers another', async () => {
    localStorage.setItem('powershift.theme', 'light');
    const backend = installFakeBackend({ theme: 'dark' });
    renderApp('/settings');

    await waitFor(() => expect(document.documentElement).toHaveClass('dark'));
    expect(screen.getByRole('radio', { name: 'Dark' })).toHaveAttribute('aria-checked', 'true');
    expect(preferenceWrites(backend.requests)).toHaveLength(0);
  });

  it('saves a change made by the user to the database', async () => {
    const backend = installFakeBackend({ theme: 'system' });
    renderApp('/settings');
    await screen.findByRole('radio', { name: 'System' });
    await waitFor(() => expect(backend.requests.some((r) => r.path === '/api/settings/preferences')).toBe(true));

    await userEvent.click(screen.getByRole('radio', { name: 'Dark' }));

    await waitFor(() => expect(preferenceWrites(backend.requests).at(-1)?.body).toEqual({ theme: 'dark' }));
    expect(backend.theme).toBe('dark');
    expect(document.documentElement).toHaveClass('dark');
  });

  it('still switches the theme when the database cannot be reached', async () => {
    const backend = installFakeBackend();
    backend.respondOnce('GET', '/api/settings/preferences', 500, { error: { code: 'internal_error', message: 'x', fields: {} } });
    renderApp('/settings');
    await userEvent.click(await screen.findByRole('radio', { name: 'Dark' }));
    expect(document.documentElement).toHaveClass('dark');
  });
});
