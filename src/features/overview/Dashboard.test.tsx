import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { BeforeAfterBars } from '@/components/ui/BeforeAfterBars';
import type { OptimizationRun } from '@/features/scheduler/types';
import { RunningPanel } from '@/features/scheduler/RunningPanel';
import type { Appliance } from '@/features/appliances/types';
import { installFakeBackend, ZERO_ESTIMATES, type FakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

const FRIDGE: Appliance = {
  id: 1, name: 'Refrigerator', category: 'kitchen', rated_power_w: 150, quantity: 1, duty_cycle: 0.4, mode: 'fixed', priority: 'high',
  allow_simultaneous: true, operating_days: [0, 1, 2, 3, 4, 5, 6], fixed_blocks: [{ start_minute: 0, end_minute: 1440 }], flexible: null,
  estimates: { ...ZERO_ESTIMATES, average_power_kw: 0.06, energy_per_operating_day_kwh: 1.44 }, warnings: [],
};

const REPORT = {
  start: '2026-11-01', end: '2026-11-30', days: 30, total_kwh: 511.35, average_daily_kwh: 17.05, energy_charge: 2886.09, tariff: null,
  daily: [], appliances: [{ appliance_id: 1, name: 'AC', category: 'cooling', mode: 'fixed', kwh: 200, share: 0.4, energy_charge: 900 }], categories: [], notes: [],
} as never;

function peak(overrides: Record<string, unknown> = {}) {
  return { weekday: 0, load_limit_kw: 5, peak_kw: 3.76, headroom_kw: 1.24, minutes_over_limit: 0, conflicts: [], peak_flexible_kw: 1.8, ...overrides } as never;
}

function run(overrides: Partial<OptimizationRun>): OptimizationRun {
  return {
    id: 1, created_at: '2026-11-10T09:30:00Z', priority: 'cost', status: 'OPTIMAL', schedule_valid: true, solve_time_ms: 10,
    baseline: { monthly_bill: 3000, peak_kw: 3.5 }, optimized: { monthly_bill: 2700, peak_kw: 3.1 }, items: [], ...overrides,
  } as unknown as OptimizationRun;
}

function open(options: Parameters<typeof installFakeBackend>[0] = {}): FakeBackend {
  const backend = installFakeBackend({ household: HOME, appliances: [FRIDGE], energy: { report: REPORT, peak: peak(), bill: { total: 3317.48, tariff: { name: 'Sample tariff' } } as never }, ...options });
  renderApp();
  return backend;
}

const tile = async (label: string) => (await screen.findByText(label, { selector: 'p' })).parentElement as HTMLElement;

describe('Overview headline tiles', () => {
  it('show real energy, bill and peak figures', async () => {
    open();
    expect(await tile('Peak demand')).toHaveTextContent('3.76 kW');
    expect(await tile('Peak demand')).toHaveTextContent('limit 5 kW');
    expect(await tile('Estimated bill')).toHaveTextContent('₹3,317.48');
    expect(await tile('Energy in November')).toHaveTextContent('511.35 kWh');
  });

  it('show potential savings only from a valid run, and say whether it is proven optimal', async () => {
    open({ runs: [run({})] });
    const t = await tile('Potential savings');
    await within(t).findByText('₹300.00');
    expect(t).toHaveTextContent('proven optimal');
  });

  it('never call a time-limited run optimal', async () => {
    open({ runs: [run({ status: 'FEASIBLE' })] });
    expect(await tile('Potential savings')).toHaveTextContent(/valid, not proven optimal/);
  });

  it('show a dash, not an invented number, when nothing has been run', async () => {
    open();
    const t = await tile('Potential savings');
    expect(t).toHaveTextContent('—');
    expect(t).toHaveTextContent('Run the Smart Scheduler to see this');
  });

  it('show a dash when the latest run has no valid schedule', async () => {
    open({ runs: [run({ status: 'INFEASIBLE', schedule_valid: false, optimized: null })] });
    const t = await tile('Potential savings');
    await within(t).findByText('The latest run found no valid schedule');
    expect(t).toHaveTextContent('—');
  });
});

describe('Overview insights', () => {
  it('warn, with real numbers, when the load limit is exceeded', async () => {
    open({ energy: { report: REPORT, peak: peak({ minutes_over_limit: 90, peak_kw: 5.4, headroom_kw: -0.4 }) } });
    expect(await screen.findByText(/Over your 5 kW limit for 90 minutes/)).toBeInTheDocument();
  });

  it('say so when the household is within its limit', async () => {
    open();
    expect(await screen.findByText(/Within your 5 kW limit/)).toBeInTheDocument();
  });

  it('say the peak cannot be checked when no limit is set', async () => {
    open({ energy: { report: REPORT, peak: peak({ load_limit_kw: null, headroom_kw: null }) } });
    expect(await screen.findByText(/No load limit is set/)).toBeInTheDocument();
  });
});

describe('Sidebar', () => {
  it('collapses to icons, keeps every link reachable by name, and remembers the choice', async () => {
    installFakeBackend();
    renderApp();
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getAllByRole('link')).toHaveLength(9);

    await userEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }));

    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toHaveAttribute('aria-expanded', 'false');
    expect(within(nav).getByRole('link', { name: 'Reports' })).toBeInTheDocument();
    expect(localStorage.getItem('powershift.sidebar')).toBe('collapsed');
  });
});

describe('Scheduler motion', () => {
  it('RunningPanel shows only true facts: goal, elapsed time and the limit, and no percentage', () => {
    render(<RunningPanel request={{ priority: 'cost', balance_weight: 50, start_step_minutes: 30, time_limit_seconds: 10 }} />);
    const panel = screen.getByRole('status', { name: 'Optimizing' });
    expect(panel).toHaveTextContent('Lowest cost');
    expect(panel).toHaveTextContent('0 s');
    expect(panel).toHaveTextContent('10 s');
    expect(panel.textContent).not.toMatch(/%/);
    expect(screen.getByRole('progressbar', { name: 'Optimization in progress' })).not.toHaveAttribute('aria-valuenow');
  });

  it('BeforeAfterBars draws a worse result in amber, never hiding it', () => {
    const { container } = render(
      <BeforeAfterBars label="Peak" before={{ label: 'Before', value: 3.76, display: '3.76 kW' }} after={{ label: 'After', value: 3.96, display: '3.96 kW' }} />,
    );
    expect(container.querySelector('.bg-warning')).not.toBeNull();
    expect(container.querySelector('.bg-accent')).toBeNull();
    expect(screen.getByText('3.96 kW')).toBeInTheDocument();
  });

  it('BeforeAfterBars draws an improvement in lime', () => {
    const { container } = render(
      <BeforeAfterBars label="Bill" before={{ label: 'Before', value: 3000, display: '₹3,000' }} after={{ label: 'After', value: 2700, display: '₹2,700' }} />,
    );
    expect(container.querySelector('.bg-accent')).not.toBeNull();
  });
});
