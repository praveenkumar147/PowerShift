import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { OptimizationRequest, OptimizationRun, ScheduleMetrics } from '@/features/scheduler/types';
import { installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

const BEFORE: ScheduleMetrics = { weekly_energy_charge: 700, monthly_bill: 3317.48, peak_kw: 3.76, peak_expected_kw: 3.07, peak_weekday: 0, minutes_over_limit: 0, conflict_minutes: 210 };
const AFTER: ScheduleMetrics = { ...BEFORE, weekly_energy_charge: 620, monthly_bill: 2950.1, peak_kw: 3.31, conflict_minutes: 0 };

function steps(kw: number) {
  return Array.from({ length: 96 }, (_, i) => ({ start_minute: i * 15, worst_kw: kw, expected_kw: kw, fixed_kw: kw, flexible_kw: 0, appliance_ids: [1] }));
}

function result(changes: Partial<OptimizationRun> = {}): OptimizationRun {
  return {
    id: 0,
    created_at: '2026-11-10T09:30:00Z',
    priority: 'cost',
    balance_weight: 50,
    start_step_minutes: 60,
    time_limit_seconds: 10,
    random_seed: 1,
    solver: 'OR-Tools CP-SAT 9.15',
    status: 'OPTIMAL',
    proven_optimal: true,
    schedule_valid: true,
    solve_time_ms: 42,
    stages: [
      { name: 'cost', status: 'OPTIMAL', value: 1, seconds: 0.01 },
      { name: 'peak', status: 'OPTIMAL', value: 2, seconds: 0.01 },
    ],
    load_limit_kw: 5,
    tariff: { id: 1, name: 'Sample TOU', tariff_type: 'tou' },
    bill_year: 2026,
    bill_month: 11,
    baseline: BEFORE,
    optimized: AFTER,
    monthly_savings: 367.38,
    peak_reduction_kw: 0.45,
    items: [
      {
        appliance_id: 7, name: 'Washing machine', power_kw: 2, duration_minutes: 90, baseline_start_minute: 1140, start_minute: 960, end_minute: 1050, moved: true,
        reasons: [{ code: 'cheaper_time', text: 'Runs when electricity is cheaper: average price while running 8.50 → 6.00 per kWh.' }],
      },
      {
        appliance_id: 9, name: 'Water heater', power_kw: 3, duration_minutes: 60, baseline_start_minute: 420, start_minute: 420, end_minute: 480, moved: false,
        reasons: [{ code: 'unchanged', text: 'Kept at its usual time. No other start time gives a better result for the chosen goal.' }],
      },
    ],
    validation: [
      { code: 'window', label: 'Each run is inside its allowed window', passed: true, detail: 'All runs inside their windows' },
      { code: 'load_limit', label: 'Household load limit respected', passed: true, detail: 'Peak 3.310 kW is within the 5 kW limit' },
    ],
    diagnostics: [],
    profile: { weekday: 0, before: steps(1), after: steps(1) },
    appliances: [{ appliance_id: 1, name: 'Fridge', category: 'kitchen', mode: 'fixed', max_kw: 0.15, allow_simultaneous: true }],
    notes: ['Estimates from your appliance settings, not measured consumption. Savings are estimated, not guaranteed.'],
    ...changes,
  };
}

async function open(solve: (request: OptimizationRequest) => OptimizationRun = () => result(), runs: OptimizationRun[] = []) {
  const backend = installFakeBackend({ household: HOME, solve, runs });
  renderApp('/scheduler');
  await screen.findByRole('heading', { level: 1, name: 'Smart Scheduler' });
  return backend;
}

const optimize = () => userEvent.click(screen.getByRole('button', { name: 'Optimize schedule' }));

describe('Smart Scheduler page', () => {
  it('starts with an empty state and sensible default settings', async () => {
    await open();
    expect(await screen.findByText('No optimization runs yet')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Balanced' })).toHaveAttribute('aria-checked', 'true');
  });

  it('runs the chosen goal and shows a verified optimal schedule', async () => {
    const backend = await open();
    await userEvent.click(screen.getByRole('radio', { name: 'Lowest cost' }));
    expect(screen.queryByLabelText('Balance')).not.toBeInTheDocument();

    await optimize();

    expect(await screen.findByText('Optimal schedule found and verified')).toBeInTheDocument();
    expect(backend.requests.find((r) => r.method === 'POST')?.body).toEqual({ priority: 'cost', balance_weight: 50, start_step_minutes: 60, time_limit_seconds: 10 });

    expect(screen.getByText('Estimated savings').parentElement).toHaveTextContent('₹367.38');
    expect(screen.getByText('Estimated bill, November').parentElement).toHaveTextContent('₹2,950.10');
    expect(screen.getByText('Estimated bill, November').parentElement).toHaveTextContent('Current schedule: ₹3,317.48');

    const table = within(screen.getByRole('table', { name: 'Recommended start and end times with reasons' }));
    const washer = within(table.getByRole('row', { name: /Washing machine/ }));
    expect(washer.getByText('19:00')).toBeInTheDocument();
    expect(washer.getByText('16:00–17:30')).toBeInTheDocument();
    expect(washer.getByText(/8.50 → 6.00 per kWh/)).toBeInTheDocument();
    expect(within(table.getByRole('row', { name: /Water heater/ })).getByText('No change (07:00–08:00)')).toBeInTheDocument();

    expect(screen.getByText(/2 of 2 checks passed/)).toBeInTheDocument();
    expect(screen.getAllByLabelText('Passed')).toHaveLength(2);
  });

  it('sends the balance weight, start step and time limit', async () => {
    const backend = await open();
    fireEvent.change(screen.getByLabelText('Balance'), { target: { value: '80' } });
    expect(screen.getByText('Cost 80% · Peak 20%')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Start times'), '15');
    await userEvent.selectOptions(screen.getByLabelText('Time limit'), '30');

    await optimize();

    await waitFor(() =>
      expect(backend.requests.find((r) => r.method === 'POST')?.body).toEqual({ priority: 'balanced', balance_weight: 80, start_step_minutes: 15, time_limit_seconds: 30 }),
    );
  });

  it('never calls a time-limited result optimal', async () => {
    await open(() => result({ status: 'FEASIBLE', proven_optimal: false }));
    await optimize();

    expect(await screen.findByText('Valid schedule found, not proven optimal')).toBeInTheDocument();
    expect(screen.queryByText(/Optimal schedule found/)).not.toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Recommended start and end times with reasons' })).toBeInTheDocument();
  });

  it('explains an infeasible problem and shows no schedule', async () => {
    await open(() =>
      result({
        status: 'INFEASIBLE', proven_optimal: false, schedule_valid: false, optimized: null, monthly_savings: null, peak_reduction_kw: null,
        items: [], validation: [], profile: null,
        diagnostics: [{ code: 'limit_too_low', message: 'The load limit is the obstacle. The lowest peak any schedule can reach is 3.50 kW, but the limit is 2.50 kW.' }],
      }),
    );
    await optimize();

    expect(await screen.findByText('No valid schedule exists')).toBeInTheDocument();
    expect(screen.getByText(/lowest peak any schedule can reach is 3.50 kW/)).toBeInTheDocument();
    expect(screen.queryByText('Recommended schedule')).not.toBeInTheDocument();
    expect(screen.queryByText('Estimated savings')).not.toBeInTheDocument();
  });

  it('does not present a schedule that failed independent validation', async () => {
    await open(() =>
      result({
        schedule_valid: false,
        validation: [{ code: 'load_limit', label: 'Household load limit respected', passed: false, detail: '30 min per week above 5 kW (peak 5.200 kW)' }],
      }),
    );
    await optimize();

    expect(await screen.findByText('The schedule failed independent validation')).toBeInTheDocument();
    expect(screen.queryByText('Recommended schedule')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Failed')).toBeInTheDocument();
    expect(screen.getByText('30 min per week above 5 kW (peak 5.200 kW)')).toBeInTheDocument();
  });

  it('shows negative savings honestly', async () => {
    await open(() => result({ priority: 'peak', monthly_savings: -41.2, optimized: { ...AFTER, monthly_bill: 3358.68 } }));
    await optimize();

    const tile = (await screen.findByText('Estimated savings')).parentElement as HTMLElement;
    expect(tile).toHaveTextContent('-₹41.20');
    expect(tile).toHaveTextContent('Costs more than your current schedule');
  });

  it('shows why a run could not start', async () => {
    const backend = await open();
    backend.respondOnce('POST', '/api/optimization/run', 422, {
      error: { code: 'validation_error', message: "Cost can't be optimised without an active tariff. Add a tariff, or choose 'Lowest peak demand'.", fields: {} },
    });
    await optimize();
    expect(await screen.findByRole('alert')).toHaveTextContent("Cost can't be optimised without an active tariff");
  });

  it('shows the latest stored run and lets the user view older ones', async () => {
    const older = result({ id: 1, priority: 'peak', status: 'INFEASIBLE', schedule_valid: false, optimized: null, items: [], validation: [], profile: null });
    const newer = result({ id: 2 });
    await open(undefined, [older, newer]);

    expect(await screen.findByText('Optimal schedule found and verified')).toBeInTheDocument();
    const history = within(screen.getByRole('table', { name: 'Optimization history' }));
    expect(history.getByText('Shown above')).toBeInTheDocument();
    expect(history.getByText('₹3,317.48 → ₹2,950.10')).toBeInTheDocument();

    await userEvent.click(history.getByRole('button', { name: /View.*run #1/ }));

    expect(await screen.findByText('No valid schedule exists')).toBeInTheDocument();
  });
});
