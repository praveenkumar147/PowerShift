import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { BackupInfo } from '@/features/settings/types';
import { captureDownloads } from '@/test/downloads';
import { ABOUT, BACKUP_SUMMARY, installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

const MANUAL: BackupInfo = { name: 'manual-20261110T090000Z.db', kind: 'manual', size_bytes: 20480, created_at: '2026-11-10T09:00:00Z' };
const AUTOMATIC: BackupInfo = { name: 'pre-migration-0004-20261109T090000Z.db', kind: 'pre-migration', size_bytes: 2_000_000, created_at: '2026-11-09T09:00:00Z' };

async function open(backups: BackupInfo[] = [MANUAL, AUTOMATIC]) {
  const backend = installFakeBackend({ household: HOME, backups: structuredClone(backups) });
  const downloads = captureDownloads();
  renderApp('/settings');
  await screen.findByRole('heading', { level: 1, name: 'Settings' });
  return { backend, downloads };
}

const dialog = () => within(screen.getByRole('dialog'));
const writes = (requests: Array<{ method: string; path: string }>) => requests.filter((r) => r.method !== 'GET' && r.path.startsWith('/api/settings'));

describe('About and storage', () => {
  it('shows the version, where the data lives and what is stored', async () => {
    await open();

    const about = within((await screen.findByRole('heading', { name: 'About and storage' })).closest('section') as HTMLElement);
    expect(await about.findByText('PowerShift 0.1.0')).toBeInTheDocument();
    expect(about.getByText(ABOUT.database_path)).toBeInTheDocument();
    expect(about.getByText(ABOUT.backups_dir)).toBeInTheDocument();
    expect(about.getByText('OR-Tools CP-SAT 9.15.6755')).toBeInTheDocument();
    expect(about.getByText('200 KB')).toBeInTheDocument();
    expect(about.getByText(/Appliances: 9 · Tariffs: 1 · Scenarios: 2 · Optimization runs: 3/)).toBeInTheDocument();
  });
});

describe('Backups', () => {
  it('lists backups with who made each, newest first', async () => {
    await open();

    const table = within(await screen.findByRole('table', { name: 'Backups, newest first' }));
    const rows = table.getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(within(rows[0] as HTMLElement).getByText('Backup you made')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('Automatic, before an upgrade')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('1.9 MB')).toBeInTheDocument();
  });

  it('shows a helpful empty state', async () => {
    await open([]);
    expect(await screen.findByText(/No backups yet/)).toBeInTheDocument();
  });

  it('creates a backup and adds it to the list', async () => {
    const { backend } = await open([]);

    await userEvent.click(await screen.findByRole('button', { name: 'Create backup' }));

    expect(await screen.findByText(/Backup created: manual-/)).toBeInTheDocument();
    expect(backend.requests.some((r) => r.method === 'POST' && r.path === '/api/settings/backup')).toBe(true);
    expect(await screen.findByRole('table', { name: 'Backups, newest first' })).toBeInTheDocument();
  });

  it('downloads a backup under its own name', async () => {
    const { downloads } = await open();
    await userEvent.click(await screen.findByRole('button', { name: `Download ${MANUAL.name}` }));
    await waitFor(() => expect(downloads.filenames).toEqual([MANUAL.name]));
  });
});

describe('Restoring a backup', () => {
  it('shows what the backup contains and warns before anything is replaced', async () => {
    const { backend } = await open();

    await userEvent.click(await screen.findByRole('button', { name: `Restore ${MANUAL.name}` }));

    expect(await dialog().findByText(/The backup is valid/)).toBeInTheDocument();
    expect(dialog().getByText('Household “Sample household”')).toBeInTheDocument();
    expect(dialog().getByText('9 appliances')).toBeInTheDocument();
    expect(dialog().getByText('1 tariff')).toBeInTheDocument();
    expect(dialog().getByText('2 scenarios')).toBeInTheDocument();
    expect(dialog().getByText(/replaces/)).toHaveTextContent('A copy of your current data is saved first');
    expect(writes(backend.requests)).toEqual([]); // checking changed nothing
  });

  it('restores only after confirmation and says where the safety copy is', async () => {
    const { backend } = await open();
    await userEvent.click(await screen.findByRole('button', { name: `Restore ${MANUAL.name}` }));
    await dialog().findByText(/The backup is valid/);

    await userEvent.click(dialog().getByRole('button', { name: 'Replace my data' }));

    expect(await dialog().findByText('Your data was restored.')).toBeInTheDocument();
    expect(dialog().getByText('pre-restore-20261111T100000Z.db')).toBeInTheDocument();
    expect(backend.requests.some((r) => r.method === 'POST' && r.path === `/api/settings/backups/${MANUAL.name}/restore`)).toBe(true);
    await userEvent.click(dialog().getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('can be cancelled without any change', async () => {
    const { backend } = await open();
    await userEvent.click(await screen.findByRole('button', { name: `Restore ${MANUAL.name}` }));
    await dialog().findByText(/The backup is valid/);

    await userEvent.click(dialog().getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(writes(backend.requests)).toEqual([]);
  });

  it('refuses a backup the server rejects, gives the reason and offers no way to replace data', async () => {
    const { backend } = await open();
    backend.respondOnce('GET', `/api/settings/backups/${MANUAL.name}/check`, 422, {
      error: { code: 'validation_error', message: 'x', fields: { file: 'The backup failed its integrity check; it is damaged.' } },
    });

    await userEvent.click(await screen.findByRole('button', { name: `Restore ${MANUAL.name}` }));

    expect(await dialog().findByText('This backup cannot be restored.')).toBeInTheDocument();
    expect(dialog().getByText('The backup failed its integrity check; it is damaged.')).toBeInTheDocument();
    expect(dialog().getByText('Your current data has not been changed.')).toBeInTheDocument();
    expect(dialog().queryByRole('button', { name: 'Replace my data' })).not.toBeInTheDocument();
    await userEvent.click(dialog().getByRole('button', { name: 'OK' }));
    expect(writes(backend.requests)).toEqual([]);
  });

  it('shows a failure that happens during the restore itself and keeps the dialog open', async () => {
    const { backend } = await open();
    await userEvent.click(await screen.findByRole('button', { name: `Restore ${MANUAL.name}` }));
    await dialog().findByText(/The backup is valid/);
    backend.respondOnce('POST', `/api/settings/backups/${MANUAL.name}/restore`, 500, {
      error: { code: 'operation_failed', message: 'The restore failed and your current data was not changed.', fields: {} },
    });

    await userEvent.click(dialog().getByRole('button', { name: 'Replace my data' }));

    expect(await dialog().findByRole('alert')).toHaveTextContent('your current data was not changed');
    expect(dialog().getByRole('button', { name: 'Replace my data' })).toBeInTheDocument();
  });

  it('mentions when an older backup will be upgraded', async () => {
    const { backend } = await open();
    backend.respondOnce('GET', `/api/settings/backups/${MANUAL.name}/check`, 200, { ...BACKUP_SUMMARY, needs_upgrade: true, schema_revision: '0003' });
    await userEvent.click(await screen.findByRole('button', { name: `Restore ${MANUAL.name}` }));
    expect(await dialog().findByText(/made by an older version and will be upgraded/)).toBeInTheDocument();
  });

  it('restores from a file the user picks, validating the file first', async () => {
    const { backend } = await open();
    const file = new File(['SQLite format 3\u0000...'], 'my-backup.db', { type: 'application/octet-stream' });

    await userEvent.upload(await screen.findByLabelText('Backup file to restore'), file);

    expect(await dialog().findByText(/The backup is valid/)).toBeInTheDocument();
    const check = backend.requests.find((r) => r.path === '/api/settings/restore/check');
    expect(check?.body).toBeInstanceOf(File); // the raw file is the request body
    expect(backend.requests.some((r) => r.path === '/api/settings/restore')).toBe(false);

    await userEvent.click(dialog().getByRole('button', { name: 'Replace my data' }));
    expect(await dialog().findByText('Your data was restored.')).toBeInTheDocument();
    expect((backend.requests.find((r) => r.path === '/api/settings/restore')?.body as File).name).toBe('my-backup.db');
  });

  it('rejects a file that is not a backup, with the server’s reason', async () => {
    const { backend } = await open();
    backend.respondOnce('POST', '/api/settings/restore/check', 422, {
      error: { code: 'validation_error', message: 'x', fields: { file: 'This is not a PowerShift backup: the file is not a SQLite database.' } },
    });

    await userEvent.upload(await screen.findByLabelText('Backup file to restore'), new File(['hello'], 'notes.db'));

    expect(await dialog().findByText(/the file is not a SQLite database/)).toBeInTheDocument();
    expect(dialog().queryByRole('button', { name: 'Replace my data' })).not.toBeInTheDocument();
    expect(backend.requests.some((r) => r.path === '/api/settings/restore')).toBe(false);
  });
});

describe('Exporting and resetting data', () => {
  it('exports a readable copy as JSON', async () => {
    const { downloads } = await open();
    await userEvent.click(await screen.findByRole('button', { name: 'Export data' }));
    expect(await screen.findByText(/Download started: powershift-data-export.json/)).toBeInTheDocument();
    expect(downloads.filenames).toEqual(['powershift-data-export.json']);
  });

  it('does nothing when reset is cancelled', async () => {
    const { backend } = await open();
    await userEvent.click(await screen.findByRole('button', { name: /Delete all data…/ }));

    await userEvent.click(dialog().getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(writes(backend.requests)).toEqual([]);
  });

  it('requires the exact word RESET before the delete button works', async () => {
    const { backend } = await open();
    await userEvent.click(await screen.findByRole('button', { name: /Delete all data…/ }));
    const confirm = dialog().getByRole('button', { name: 'Delete all data' });
    expect(confirm).toBeDisabled();

    for (const wrong of ['reset', 'RESE', 'RESET ', 'yes']) {
      await userEvent.clear(dialog().getByLabelText('Type RESET to confirm'));
      await userEvent.type(dialog().getByLabelText('Type RESET to confirm'), wrong);
      expect(confirm).toBeDisabled();
    }
    expect(writes(backend.requests)).toEqual([]);

    await userEvent.clear(dialog().getByLabelText('Type RESET to confirm'));
    await userEvent.type(dialog().getByLabelText('Type RESET to confirm'), 'RESET');
    expect(confirm).toBeEnabled();
  });

  it('deletes everything, says what was removed and where the safety backup is', async () => {
    const { backend } = await open();
    await userEvent.click(await screen.findByRole('button', { name: /Delete all data…/ }));
    await userEvent.type(dialog().getByLabelText('Type RESET to confirm'), 'RESET');

    await userEvent.click(dialog().getByRole('button', { name: 'Delete all data' }));

    expect(await dialog().findByText('All data was deleted.')).toBeInTheDocument();
    expect(dialog().getByText(/9 appliances, 1 tariffs, 2 scenarios, 3 optimization runs, 1 household profile/)).toBeInTheDocument();
    expect(dialog().getByText('pre-reset-20261111T100000Z.db')).toBeInTheDocument();
    expect(backend.requests.find((r) => r.method === 'POST' && r.path === '/api/settings/reset')?.body).toEqual({ confirm: 'RESET' });
  });

  it('shows why a reset failed and keeps the dialog open', async () => {
    const { backend } = await open();
    backend.respondOnce('POST', '/api/settings/reset', 500, {
      error: { code: 'operation_failed', message: 'A safety backup could not be created, so nothing was deleted.', fields: {} },
    });
    await userEvent.click(await screen.findByRole('button', { name: /Delete all data…/ }));
    await userEvent.type(dialog().getByLabelText('Type RESET to confirm'), 'RESET');

    await userEvent.click(dialog().getByRole('button', { name: 'Delete all data' }));

    expect(await dialog().findByRole('alert')).toHaveTextContent('nothing was deleted');
  });
});
