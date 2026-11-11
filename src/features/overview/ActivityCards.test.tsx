import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Appliance } from '@/features/appliances/types';
import type { OptimizationRun } from '@/features/scheduler/types';
import type { Scenario } from '@/features/simulation/types';
import { installFakeBackend, ZERO_ESTIMATES } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const FRIDGE: Appliance = {
  id: 1, name: 'Refrigerator', category: 'kitchen', rated_power_w: 150, quantity: 1, duty_cycle: 0.4, mode: 'fixed', priority: 'high',
  allow_simultaneous: true, operating_days: [0, 1, 2, 3, 4, 5, 6], fixed_blocks: [{ start_minute: 0, end_minute: 1440 }], flexible: null,
  estimates: { ...ZERO_ESTIMATES, average_power_kw: 0.06, energy_per_operating_day_kwh: 1.44 }, warnings: [],
};

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

function run(overrides: Partial<OptimizationRun>): OptimizationRun {
  return {
    id: 1, created_at: '2026-11-10T09:30:00Z', priority: 'cost', status: 'OPTIMAL', schedule_valid: true, solve_time_ms: 10,
    baseline: { monthly_bill: 3000, peak_kw: 3.5 }, optimized: { monthly_bill: 2700, peak_kw: 3.1 }, items: [],
    ...overrides,
  } as unknown as OptimizationRun;
}

function scenario(stale: boolean): Scenario {
  return {
    id: 1, name: 'Add AC', description: null, priority: 'cost', balance_weight: 50, changes: [], change_descriptions: [],
    created_at: '2026-11-11T08:00:00Z', updated_at: '2026-11-11T08:00:00Z', result_is_stale: stale,
    latest_result: { id: 10, scenario_name: 'Add AC', created_at: '2026-11-11T09:00:00Z', bill_change: 1088.64 } as never,
  };
}

const card = async (name: string) => within(await screen.findByRole('region', { name }));

describe('Overview activity cards', () => {
  it('invite the user to try each module when nothing has been done', async () => {
    installFakeBackend({ household: HOME });
    renderApp();

    expect(await screen.findByText(/No optimization has been run yet/)).toBeInTheDocument();
    expect(screen.getByText(/No scenarios yet/)).toBeInTheDocument();
    expect(screen.getByText(/You have not made a backup yet/)).toBeInTheDocument();
    expect((await card('Smart Scheduler')).getByRole('link', { name: 'Open Smart Scheduler' })).toHaveAttribute('href', '/scheduler');
  });

  it('summarise the latest valid run and say when it is proven optimal', async () => {
    installFakeBackend({ household: HOME, runs: [run({})] });
    renderApp();

    const scheduler = await card('Smart Scheduler');
    expect(await scheduler.findByText('−₹300.00', { exact: false })).toBeInTheDocument();
    expect(scheduler.getByText('Proven optimal for the model.')).toBeInTheDocument();
  });

  it('never call a time-limited run optimal, and report a run with no valid schedule honestly', async () => {
    installFakeBackend({ household: HOME, runs: [run({ id: 1, status: 'FEASIBLE' }), run({ id: 2, status: 'INFEASIBLE', schedule_valid: false, optimized: null })] });
    renderApp();
    expect(await screen.findByText(/No valid schedule was found in this run \(INFEASIBLE\)/)).toBeInTheDocument();
    expect(screen.queryByText('Proven optimal for the model.')).not.toBeInTheDocument();
  });

  it('show the latest scenario result and warn when it is out of date', async () => {
    installFakeBackend({ household: HOME, scenarios: [scenario(true)] });
    renderApp();

    const lab = await card('Simulation Lab');
    expect(await lab.findByText('Add AC')).toBeInTheDocument();
    expect(lab.getByText(/edited since; run it again/)).toBeInTheDocument();
  });

  it('show the last backup the user made', async () => {
    installFakeBackend({ household: HOME, backups: [{ name: 'manual-20261111T070539Z.db', kind: 'manual', size_bytes: 1000, created_at: '2026-11-11T07:05:39Z' }] });
    renderApp();
    expect(await screen.findByText(/Last backup you made/)).toBeInTheDocument();
    expect(screen.getByText('1 file in the backups folder.')).toBeInTheDocument();
  });

  it('show an error in one card without hiding the others', async () => {
    const backend = installFakeBackend({ household: HOME });
    backend.respondOnce('GET', '/api/simulations', 500, { error: { code: 'internal_error', message: 'Scenarios unavailable', fields: {} } });
    renderApp();
    expect(await screen.findByText('Scenarios unavailable')).toBeInTheDocument();
    expect(screen.getByText(/No optimization has been run yet/)).toBeInTheDocument();
  });
});

describe('Overview month tiles', () => {
  it('say so when the estimates cannot be loaded', async () => {
    const backend = installFakeBackend({ household: HOME, appliances: [FRIDGE] });
    backend.respondOnce('GET', '/api/energy/report', 500, { error: { code: 'internal_error', message: 'Energy unavailable', fields: {} } });
    renderApp();
    expect(await screen.findByText(/estimates could not be loaded: Energy unavailable/)).toBeInTheDocument();
  });
});
