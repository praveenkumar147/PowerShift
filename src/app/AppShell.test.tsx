import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NAV_ITEMS } from '@/app/navigation';
import { jsonResponse, renderApp } from '@/test/render';

const HEALTH = {
  status: 'ok',
  version: '0.1.0',
  schema_revision: '0001',
  database_path: 'C:\\data\\powershift.db',
};

describe('App shell', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(HEALTH)));
  });

  it('lists all nine sections in the sidebar', async () => {
    renderApp();

    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(NAV_ITEMS.map((i) => i.label));
  });

  it('shows real backend status on the overview page', async () => {
    renderApp();

    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
    expect(screen.getByText('0001')).toBeInTheDocument();
    expect(screen.getByText('C:\\data\\powershift.db')).toBeInTheDocument();
  });

  it('shows a backend error with a working retry button', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'internal_error', message: 'Database unavailable' } }, 500))
      .mockResolvedValueOnce(jsonResponse(HEALTH));
    vi.stubGlobal('fetch', fetchMock);
    renderApp();

    expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable');
    await userEvent.click(screen.getByRole('button', { name: 'Check again' }));
    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
  });

  it('navigates to a module and marks it active', async () => {
    renderApp();
    const nav = await screen.findByRole('navigation', { name: 'Main' });

    await userEvent.click(within(nav).getByRole('link', { name: 'Smart Scheduler' }));

    expect(screen.getByRole('heading', { level: 1, name: 'Smart Scheduler' })).toBeInTheDocument();
    expect(screen.getByText('This module is planned for development Stage 5.')).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Smart Scheduler' })).toHaveAttribute('aria-current', 'page');
  });
});
