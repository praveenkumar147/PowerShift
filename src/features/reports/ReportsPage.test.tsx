import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { OptimizationRun } from '@/features/scheduler/types';
import type { Scenario } from '@/features/simulation/types';
import { captureDownloads } from '@/test/downloads';
import { installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

function run(id: number): OptimizationRun {
  return {
    id, created_at: '2026-11-10T09:30:00Z', priority: id === 1 ? 'cost' : 'peak', status: 'OPTIMAL', schedule_valid: true, solve_time_ms: 10,
    baseline: { monthly_bill: 3000, peak_kw: 3.5 }, optimized: null, items: [],
  } as unknown as OptimizationRun;
}

function scenario(id: number, name: string, withResult: boolean): Scenario {
  return {
    id, name, description: null, priority: 'cost', balance_weight: 50, changes: [], change_descriptions: [],
    created_at: '2026-11-11T08:00:00Z', updated_at: '2026-11-11T08:00:00Z', result_is_stale: false,
    latest_result: withResult ? ({ id: id * 10, scenario_name: name } as never) : null,
  };
}

async function open(options: Parameters<typeof installFakeBackend>[0] = {}) {
  const backend = installFakeBackend({ household: HOME, ...options });
  const downloads = captureDownloads();
  renderApp('/reports');
  await screen.findByRole('heading', { level: 1, name: 'Reports' });
  return { backend, downloads };
}

const choose = (name: string) => userEvent.click(screen.getByRole('radio', { name: new RegExp(name) }));
const exportButton = (format: string) => screen.getByRole('button', { name: `Export ${format}` });
const lastExport = (requests: Array<{ method: string; path: string; body: unknown }>) => requests.filter((r) => r.path === '/api/reports/export').at(-1)?.body;

describe('Reports page', () => {
  it('offers all seven reports and says what every report states', async () => {
    await open();

    const group = within(screen.getByRole('radiogroup', { name: 'Report' }));
    expect(group.getAllByRole('radio').map((r) => r.querySelector('span')?.textContent)).toEqual([
      'Daily energy report', 'Monthly energy report', 'Appliance consumption report', 'Electricity bill estimate',
      'Peak load report', 'Optimization comparison report', 'Simulation comparison report',
    ]);
    const states = within(screen.getByRole('region', { name: 'What every report states' }));
    expect(states.getByText(/all figures are estimates, not measurements/)).toBeInTheDocument();
    expect(states.getByText('The tariff it depends on')).toBeInTheDocument();
  });

  it('exports the daily report as CSV with the chosen range and saves the file the server names', async () => {
    const { backend, downloads } = await open();
    await userEvent.click(screen.getByRole('radio', { name: /CSV/ }));
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'laundry');

    await userEvent.click(exportButton('CSV'));

    expect(await screen.findByText(/Download started: powershift-daily-energy-20261111.csv/)).toBeInTheDocument();
    const body = lastExport(backend.requests) as { type: string; format: string; params: Record<string, string> };
    expect(body).toMatchObject({ type: 'daily_energy', format: 'csv', params: { category: 'laundry' } });
    expect(body.params.start).toMatch(/^\d{4}-\d{2}-01$/);
    expect(body.params.end).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(downloads.filenames).toEqual(['powershift-daily-energy-20261111.csv']);
    expect(await downloads.blobs[0]?.text()).toBe('report-bytes');
  });

  it('defaults to PDF and shows only the options a report uses', async () => {
    const { backend } = await open();
    expect(screen.getByRole('radio', { name: /PDF/ })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByLabelText('From')).toBeInTheDocument();

    await choose('Monthly energy report');
    expect(screen.queryByLabelText('From')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Year')).toBeInTheDocument();
    await userEvent.click(exportButton('PDF'));

    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ type: 'monthly_energy', format: 'pdf', params: { year: new Date().getFullYear() } }));
  });

  it('sends the month and year for the bill estimate', async () => {
    const { backend } = await open();
    await choose('Electricity bill estimate');
    await userEvent.selectOptions(screen.getByLabelText('Month'), '3');

    await userEvent.click(exportButton('PDF'));

    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ type: 'bill_estimate', params: { month: 3, year: new Date().getFullYear() } }));
  });

  it('lets the peak report follow the highest-peak day or a chosen weekday', async () => {
    const { backend } = await open();
    await choose('Peak load report');
    await userEvent.click(exportButton('PDF'));
    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ type: 'peak_load', params: {} }));
    expect((lastExport(backend.requests) as { params: object }).params).not.toHaveProperty('weekday');

    await userEvent.selectOptions(screen.getByLabelText('Day'), '1');
    await userEvent.click(exportButton('PDF'));
    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ params: { weekday: 1 } }));
  });

  it('explains that an optimization report needs a run first, and blocks the export', async () => {
    await open();
    await choose('Optimization comparison report');

    expect(screen.getByText(/No optimization runs yet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Smart Scheduler' })).toHaveAttribute('href', '/scheduler');
    expect(exportButton('PDF')).toBeDisabled();
  });

  it('exports the latest run by default, or a specific one', async () => {
    const { backend } = await open({ runs: [run(1), run(2)] });
    await choose('Optimization comparison report');
    await userEvent.click(exportButton('PDF'));
    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ type: 'optimization_comparison', params: {} }));
    expect((lastExport(backend.requests) as { params: object }).params).not.toHaveProperty('run_id');

    await userEvent.selectOptions(screen.getByLabelText('Optimization run'), '1');
    await userEvent.click(exportButton('PDF'));
    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ params: { run_id: 1 } }));
  });

  it('needs a scenario that has been run; scenarios without a result are not offered', async () => {
    await open({ scenarios: [scenario(1, 'Never run', false)] });
    await choose('Simulation comparison report');
    expect(screen.getByText(/No scenario has been run yet/)).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: 'Never run' })).not.toBeInTheDocument();
    expect(exportButton('PDF')).toBeDisabled();
  });

  it('includes every scenario that has results unless some are unticked', async () => {
    const { backend } = await open({ scenarios: [scenario(1, 'Add AC', true), scenario(2, 'Wash less', true), scenario(3, 'Not run', false)] });
    await choose('Simulation comparison report');
    expect(screen.getAllByRole('checkbox').map((c) => (c as HTMLInputElement).checked)).toEqual([true, true]);

    await userEvent.click(exportButton('PDF'));
    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ type: 'simulation_comparison', params: {} }));

    await userEvent.click(screen.getByRole('checkbox', { name: 'Wash less' }));
    await userEvent.click(exportButton('PDF'));
    await waitFor(() => expect(lastExport(backend.requests)).toMatchObject({ params: { scenario_ids: [1] } }));

    await userEvent.click(screen.getByRole('checkbox', { name: 'Add AC' }));
    expect(exportButton('PDF')).toBeDisabled();
  });

  it('shows what the server rejected next to the field', async () => {
    const { backend } = await open();
    backend.respondOnce('POST', '/api/reports/export', 422, {
      error: { code: 'validation_error', message: 'Choose a range of at most 366 days.', fields: { end: 'Choose a range of at most 366 days.' } },
    });
    await userEvent.click(exportButton('PDF'));
    expect(await screen.findByText('Choose a range of at most 366 days.')).toBeInTheDocument();
    expect(screen.getByLabelText('To')).toHaveAttribute('aria-invalid', 'true');
  });

  it('reports an unreachable backend plainly', async () => {
    const { backend } = await open();
    backend.respondOnce('POST', '/api/reports/export', 500, { error: { code: 'internal_error', message: 'Something went wrong. Details were saved to the log.', fields: {} } });
    await userEvent.click(exportButton('PDF'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong');
  });
});
