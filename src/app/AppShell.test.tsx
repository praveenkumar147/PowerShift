import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { NAV_ITEMS } from '@/app/navigation';
import { HEALTH, installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

describe('App shell', () => {
  it('lists all nine sections in the sidebar', async () => {
    installFakeBackend();
    renderApp();

    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(NAV_ITEMS.map((i) => i.label));
  });

  it('shows real backend status on the overview page', async () => {
    installFakeBackend();
    renderApp();

    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
    expect(screen.getByText(HEALTH.schema_revision ?? '')).toBeInTheDocument();
    expect(screen.getByText(HEALTH.database_path)).toBeInTheDocument();
  });

  it('shows a backend error with a working retry button', async () => {
    const backend = installFakeBackend();
    backend.respondOnce('GET', '/api/health', 500, { error: { code: 'internal_error', message: 'Database unavailable' } });
    renderApp();

    expect(await screen.findByText('Database unavailable')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Check again' }));
    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
  });

  it('navigates to a module and marks it active', async () => {
    installFakeBackend();
    renderApp();
    const nav = await screen.findByRole('navigation', { name: 'Main' });

    await userEvent.click(within(nav).getByRole('link', { name: 'Reports' }));

    expect(screen.getByRole('heading', { level: 1, name: 'Reports' })).toBeInTheDocument();
    expect(screen.getByText('This module is planned for development Stage 7.')).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Reports' })).toHaveAttribute('aria-current', 'page');
  });

  it('loads labelled sample data from the empty overview', async () => {
    const backend = installFakeBackend();
    renderApp();

    await userEvent.click(await screen.findByRole('button', { name: 'Load sample data' }));

    expect(backend.requests.some((r) => r.method === 'POST' && r.path === '/api/demo')).toBe(true);
  });

  it('guides a new user to set up the household first', async () => {
    installFakeBackend();
    renderApp();

    await userEvent.click(await screen.findByRole('link', { name: 'Set up household' }));

    expect(screen.getByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument();
  });
});
