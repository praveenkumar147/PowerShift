import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Appliance } from '@/features/appliances/types';
import type { Scenario, SimMetrics, SimulationResult } from '@/features/simulation/types';
import { installFakeBackend, ZERO_ESTIMATES } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

const TELEVISION: Appliance = {
  id: 4, name: 'Television', category: 'entertainment', rated_power_w: 100, quantity: 1, duty_cycle: 1, mode: 'fixed', priority: 'medium',
  allow_simultaneous: true, operating_days: [0, 1, 2, 3, 4, 5, 6], fixed_blocks: [{ start_minute: 1140, end_minute: 1320 }], flexible: null,
  estimates: ZERO_ESTIMATES, warnings: [],
};

const BASELINE: SimMetrics = { monthly_kwh: 500, monthly_bill: 3000, peak_kw: 3.5, peak_expected_kw: 3, minutes_over_limit: 0, conflict_minutes: 0 };

function result(changes: Partial<SimulationResult> = {}): SimulationResult {
  return {
    id: 0, scenario_id: 0, scenario_name: 'Add AC', created_at: '2026-11-11T09:00:00Z', priority: 'cost', balance_weight: 50,
    change_descriptions: ['Add "Study AC" (1.5 kW, fixed, 8 h on, 7 days a week)'],
    tariff: { id: 1, name: 'Sample TOU', tariff_type: 'tou' }, load_limit_kw: 5, bill_year: 2026, bill_month: 11,
    baseline: BASELINE,
    scenario: { ...BASELINE, monthly_kwh: 716, monthly_bill: 3284.62, peak_kw: 5.1, minutes_over_limit: 90 },
    optimized: { ...BASELINE, monthly_kwh: 716, monthly_bill: 3180, peak_kw: 4.8 },
    status: 'OPTIMAL', proven_optimal: true, schedule_valid: true, solve_time_ms: 40, optimization_note: null,
    kwh_change: 216, bill_change: 284.62, optimized_bill_change: 180, optimization_savings: 104.62, peak_change_kw: 1.3,
    items: [{
      appliance_id: 7, name: 'Washing machine', power_kw: 2, duration_minutes: 90, baseline_start_minute: 1140, start_minute: 960, end_minute: 1050, moved: true,
      reasons: [{ code: 'cheaper_time', text: 'Runs when electricity is cheaper: average price while running 8.50 → 6.00 per kWh.' }],
    }],
    validation: [{ code: 'window', label: 'Each run is inside its allowed window', passed: true, detail: 'All runs inside their windows' }],
    diagnostics: [],
    notes: ['Calculated on a copy of your data. Your real appliances, tariffs and household were not changed.'],
    ...changes,
  };
}

function scenario(id: number, name: string, latest: SimulationResult | null = null, changes: Partial<Scenario> = {}): Scenario {
  return {
    id, name, description: null, priority: 'cost', balance_weight: 50,
    changes: [{ type: 'set_load_limit', max_load_kw: 8 }], change_descriptions: ['Load limit 5 kW → 8 kW'],
    created_at: '2026-11-11T08:00:00Z', updated_at: '2026-11-11T08:00:00Z', latest_result: latest, result_is_stale: false, ...changes,
  };
}

async function open(scenarios: Scenario[] = [], simulate?: (s: Scenario) => SimulationResult) {
  const backend = installFakeBackend({ household: HOME, appliances: [TELEVISION], scenarios: structuredClone(scenarios), ...(simulate ? { simulate } : {}) });
  renderApp('/simulation');
  await screen.findByRole('heading', { level: 1, name: 'Simulation Lab' });
  return backend;
}

const dialog = () => within(screen.getByRole('dialog'));
const realWrites = (requests: Array<{ method: string; path: string }>) =>
  requests.filter((r) => r.method !== 'GET' && !r.path.startsWith('/api/simulations'));

describe('Simulation Lab page', () => {
  it('explains what scenarios are and that real data is never changed', async () => {
    await open();
    expect(await screen.findByText('No scenarios yet')).toBeInTheDocument();
    expect(screen.getByText(/never changed/)).toBeInTheDocument();
  });

  it('builds a scenario from simple changes and saves it', async () => {
    const backend = await open();
    await userEvent.click(screen.getByRole('button', { name: 'New scenario' }));

    await userEvent.type(dialog().getByLabelText('Name'), 'No TV');
    await userEvent.click(dialog().getByRole('radio', { name: 'Lowest peak' }));
    await userEvent.selectOptions(dialog().getByLabelText('What to change'), 'remove');
    await userEvent.click(dialog().getByRole('button', { name: 'Add change' }));
    await userEvent.selectOptions(dialog().getByLabelText('What to change'), 'limit');
    await userEvent.type(dialog().getByLabelText('New load limit (kW)'), '8');
    await userEvent.click(dialog().getByRole('button', { name: 'Add change' }));

    const list = within(dialog().getByRole('region', { name: 'Changes' }));
    expect(list.getByText('Remove "Television"')).toBeInTheDocument();
    expect(list.getByText('Set load limit to 8 kW')).toBeInTheDocument();
    await userEvent.click(dialog().getByRole('button', { name: 'Save scenario' }));

    expect(await screen.findByRole('article', { name: 'No TV' })).toBeInTheDocument();
    expect(backend.requests.find((r) => r.method === 'POST')?.body).toEqual({
      name: 'No TV', description: null, priority: 'peak', balance_weight: 50,
      changes: [{ type: 'remove_appliance', appliance_id: 4 }, { type: 'set_load_limit', max_load_kw: 8 }],
    });
  });

  it('adds a new appliance to a scenario without saving it to the household', async () => {
    const backend = await open();
    await userEvent.click(screen.getByRole('button', { name: 'New scenario' }));
    await userEvent.type(dialog().getByLabelText('Name'), 'Add AC');

    await userEvent.click(dialog().getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('dialog', { name: 'Add an appliance to this scenario' })).toBeInTheDocument();
    await userEvent.type(dialog().getByLabelText('Name'), 'Study AC');
    await userEvent.type(dialog().getByLabelText('Rated power (W)'), '1500');
    await userEvent.click(dialog().getByRole('button', { name: 'Use in scenario' }));

    // Back in the scenario form, with the typed name still there and the change listed.
    expect(dialog().getByLabelText('Name')).toHaveValue('Add AC');
    expect(dialog().getByText('Add "Study AC"')).toBeInTheDocument();
    await userEvent.click(dialog().getByRole('button', { name: 'Save scenario' }));

    await screen.findByRole('article', { name: 'Add AC' });
    const post = backend.requests.find((r) => r.method === 'POST' && r.path === '/api/simulations');
    expect(post?.body).toMatchObject({ changes: [{ type: 'add_appliance', appliance: { name: 'Study AC', rated_power_w: 1500 } }] });
    expect(realWrites(backend.requests)).toEqual([]);
    expect(backend.appliances.map((a) => a.name)).toEqual(['Television']);
  });

  it('starts a change from an existing appliance, pre-filled', async () => {
    await open();
    await userEvent.click(screen.getByRole('button', { name: 'New scenario' }));

    await userEvent.selectOptions(dialog().getByLabelText('What to change'), 'replace');
    await userEvent.click(dialog().getByRole('button', { name: 'Continue' }));

    expect(screen.getByRole('dialog', { name: 'Change Television in this scenario' })).toBeInTheDocument();
    expect(dialog().getByLabelText('Rated power (W)')).toHaveValue(100);
    fireEvent.change(dialog().getByLabelText('Rated power (W)'), { target: { value: '150' } });
    await userEvent.click(dialog().getByRole('button', { name: 'Use in scenario' }));
    expect(dialog().getByText('Change "Television"')).toBeInTheDocument();
  });

  it('shows backend problems next to the change that caused them', async () => {
    const backend = await open();
    backend.respondOnce('POST', '/api/simulations', 422, {
      error: { code: 'validation_error', message: 'Some changes are inconsistent.', fields: { 'changes.0.appliance_id': 'This appliance no longer exists or was already removed by another change.' } },
    });
    await userEvent.click(screen.getByRole('button', { name: 'New scenario' }));
    await userEvent.type(dialog().getByLabelText('Name'), 'Broken');
    await userEvent.selectOptions(dialog().getByLabelText('What to change'), 'remove');
    await userEvent.click(dialog().getByRole('button', { name: 'Add change' }));

    await userEvent.click(dialog().getByRole('button', { name: 'Save scenario' }));

    const item = (await dialog().findByText('Remove "Television"')).closest('li') as HTMLElement;
    expect(within(item).getByText(/no longer exists/)).toBeInTheDocument();
  });

  it('shows a duplicate name conflict on the name field', async () => {
    const backend = await open([scenario(1, 'Add AC')]);
    backend.respondOnce('POST', '/api/simulations', 409, {
      error: { code: 'conflict', message: 'A scenario named "add ac" already exists.', fields: { name: 'This name is already used by another scenario.' } },
    });
    await userEvent.click(screen.getByRole('button', { name: 'New scenario' }));
    await userEvent.type(dialog().getByLabelText('Name'), 'add ac');
    await userEvent.click(dialog().getByRole('button', { name: 'Save scenario' }));
    expect(await dialog().findByText('This name is already used by another scenario.')).toBeInTheDocument();
  });

  it('runs a scenario and shows signed differences against the current household', async () => {
    const backend = await open([scenario(1, 'Add AC')], () => result());
    const card = within(await screen.findByRole('article', { name: 'Add AC' }));
    expect(card.getByText('Not run yet.')).toBeInTheDocument();

    await userEvent.click(card.getByRole('button', { name: 'Run scenario' }));

    await waitFor(() => expect(backend.requests.some((r) => r.path === '/api/simulations/1/run')).toBe(true));
    expect(await card.findByText('+216 kWh')).toBeInTheDocument();
    expect(card.getByText('+₹284.62')).toBeInTheDocument();
    expect(card.getByText('+₹180.00')).toBeInTheDocument();
    expect(card.getByText('+1.3 kW')).toBeInTheDocument();
    expect(card.getByText(/your real household was not changed/)).toBeInTheDocument();
    // Details open after a run.
    expect(card.getByText('Optimal schedule found and verified.')).toBeInTheDocument();
    expect(card.getByText(/8.50 → 6.00 per kWh/)).toBeInTheDocument();
  });

  it('shows savings with a minus sign and never hides a cost increase', async () => {
    await open(
      [scenario(1, 'Wash less', result({ kwh_change: -30, bill_change: -41.2, optimized_bill_change: -60, peak_change_kw: -0.4 }))],
    );
    const card = within(await screen.findByRole('article', { name: 'Wash less' }));
    expect(card.getByText('−30 kWh')).toBeInTheDocument();
    expect(card.getByText('−₹41.20')).toBeInTheDocument();
    expect(card.getByText('−0.4 kW')).toBeInTheDocument();
  });

  it('explains a scenario that has no valid schedule, and still shows its usual-times numbers', async () => {
    await open([
      scenario(1, 'Tight limit', result({
        status: 'INFEASIBLE', schedule_valid: false, proven_optimal: false, optimized: null, optimized_bill_change: null, optimization_savings: null, items: [], validation: [],
        optimization_note: 'No valid schedule exists for this scenario (see the reasons below).',
        diagnostics: [{ code: 'limit_too_low', message: 'The lowest peak any schedule can reach is 3.50 kW, but the limit is 2.50 kW.' }],
      })),
    ]);
    const card = within(await screen.findByRole('article', { name: 'Tight limit' }));
    expect(card.getByText('No valid schedule')).toBeInTheDocument(); // bill-after hint
    await userEvent.click(card.getByRole('button', { name: 'Show details' }));
    expect(card.getByText('No valid schedule.')).toBeInTheDocument();
    expect(card.getByText(/lowest peak any schedule can reach is 3.50 kW/)).toBeInTheDocument();
    expect(card.queryByText('Recommended schedule')).not.toBeInTheDocument();
    expect(card.getByText('+₹284.62')).toBeInTheDocument();
  });

  it('marks a scenario edited since its last run', async () => {
    await open([scenario(1, 'Add AC', result(), { result_is_stale: true })]);
    expect(await screen.findByText('Edited since last run')).toBeInTheDocument();
  });

  it('compares several scenarios side by side and warns when baselines differ', async () => {
    const other = result({ scenario_name: 'Wash less', kwh_change: -30, bill_change: -41.2, optimized_bill_change: -60, optimization_savings: 18.8,
      scenario: { ...BASELINE, monthly_kwh: 470, monthly_bill: 2958.8 }, optimized: { ...BASELINE, monthly_kwh: 470, monthly_bill: 2940, peak_kw: 3.1 } });
    await open([scenario(1, 'Add AC', result()), scenario(2, 'Wash less', other)]);

    const table = within(await screen.findByRole('table', { name: 'Scenario comparison' }));
    expect(table.getByRole('columnheader', { name: /Add AC/ })).toBeInTheDocument();
    expect(table.getByRole('columnheader', { name: /Wash less/ })).toBeInTheDocument();
    const billRow = table.getByRole('row', { name: /Estimated bill, after scheduling/ });
    expect(within(billRow).getByText('₹3,180.00')).toBeInTheDocument();
    expect(within(billRow).getByText('−₹60.00')).toBeInTheDocument();
    expect(screen.queryByText(/comparison is not fair/)).not.toBeInTheDocument();
  });

  it('warns that the comparison is unfair when results were calculated on different households', async () => {
    const changed = result({ baseline: { ...BASELINE, monthly_bill: 3500 } });
    await open([scenario(1, 'Add AC', result()), scenario(2, 'Other', changed)]);
    expect(await screen.findByText(/comparison is not fair/)).toBeInTheDocument();
  });

  it('edits a scenario with its changes pre-filled', async () => {
    const backend = await open([scenario(1, 'Add AC')]);
    await userEvent.click(await screen.findByRole('button', { name: 'Edit Add AC' }));

    expect(dialog().getByLabelText('Name')).toHaveValue('Add AC');
    expect(dialog().getByText('Set load limit to 8 kW')).toBeInTheDocument();
    await userEvent.click(dialog().getByRole('button', { name: 'Remove change 1' }));
    await userEvent.click(dialog().getByRole('button', { name: 'Save scenario' }));

    await waitFor(() => expect(backend.requests.some((r) => r.method === 'PUT' && r.path === '/api/simulations/1')).toBe(true));
    expect(backend.requests.find((r) => r.method === 'PUT')?.body).toMatchObject({ changes: [] });
  });

  it('deletes a scenario only after confirmation', async () => {
    const backend = await open([scenario(1, 'Add AC')]);
    await userEvent.click(await screen.findByRole('button', { name: 'Delete Add AC' }));
    expect(dialog().getByText(/Your real household is not affected/)).toBeInTheDocument();
    await userEvent.click(dialog().getByRole('button', { name: 'Cancel' }));
    expect(backend.requests.some((r) => r.method === 'DELETE')).toBe(false);

    await userEvent.click(screen.getByRole('button', { name: 'Delete Add AC' }));
    await userEvent.click(dialog().getByRole('button', { name: 'Delete scenario' }));

    expect(await screen.findByText('No scenarios yet')).toBeInTheDocument();
  });

  it('shows why a scenario could not be run', async () => {
    const backend = await open([scenario(1, 'Add AC')], () => result());
    backend.respondOnce('POST', '/api/simulations/1/run', 422, {
      error: { code: 'validation_error', message: 'This scenario can no longer be applied to your current household.', fields: { 'changes.0.appliance_id': 'This appliance no longer exists or was already removed by another change.' } },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Run scenario' }));
    expect(await screen.findByText('This scenario can no longer be applied to your current household.')).toBeInTheDocument();
    expect(screen.getByText(/no longer exists/)).toBeInTheDocument();
  });
});
