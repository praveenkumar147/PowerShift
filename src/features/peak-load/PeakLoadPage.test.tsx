import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { PeakLoadAnalysis } from '@/features/peak-load/types';
import { installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 2, currency_code: 'INR', time_format: '24h' as const };

function steps(): PeakLoadAnalysis['steps'] {
  return Array.from({ length: 96 }, (_, i) => {
    const washing = i >= 76 && i < 82; // 19:00-20:30
    return {
      start_minute: i * 15,
      worst_kw: washing ? 2.15 : 0.15,
      expected_kw: washing ? 1.06 : 0.06,
      fixed_kw: 0.15,
      flexible_kw: washing ? 2 : 0,
      appliance_ids: washing ? [2, 1] : [1],
    };
  });
}

function analysis(weekday: number | null, limit: number | null = 2): PeakLoadAnalysis {
  const day = weekday ?? 0;
  const washerDay = [0, 3, 5].includes(day);
  const violation = { start_minute: 1140, end_minute: 1230, minutes: 90, max_kw: 2.15, appliances: [{ appliance_id: 2, name: 'Washing machine' }, { appliance_id: 1, name: 'Refrigerator' }] };
  return {
    weekday: day,
    selected_automatically: weekday === null,
    load_limit_kw: limit,
    peak_kw: washerDay ? 2.15 : 0.15,
    peak_expected_kw: washerDay ? 1.06 : 0.06,
    headroom_kw: limit === null ? null : limit - (washerDay ? 2.15 : 0.15),
    minutes_over_limit: washerDay && limit !== null ? 90 : 0,
    peak_windows: [{ start_minute: 1140, end_minute: 1230, minutes: 90 }],
    peak_fixed_kw: 0.15,
    peak_flexible_kw: washerDay ? 2 : 0,
    peak_contributors: [
      { appliance_id: 2, name: 'Washing machine', mode: 'flexible', kw: 2 },
      { appliance_id: 1, name: 'Refrigerator', mode: 'fixed', kw: 0.15 },
    ],
    steps: steps(),
    violations: washerDay && limit !== null ? [violation] : [],
    high_demand: washerDay ? [violation] : [],
    overlaps: [],
    conflicts: washerDay ? [{ ...violation, start_minute: 1200, end_minute: 1230, minutes: 30, max_kw: 3.8, appliances: [{ appliance_id: 2, name: 'Washing machine' }, { appliance_id: 3, name: 'Dishwasher' }] }] : [],
    week: [0, 1, 2, 3, 4, 5, 6].map((d) => ({
      weekday: d,
      peak_kw: [0, 3, 5].includes(d) ? 2.15 : 0.15,
      peak_expected_kw: 0.06,
      peak_start_minute: 1140,
      minutes_over_limit: [0, 3, 5].includes(d) ? 90 : 0,
    })),
    appliances: [
      { appliance_id: 2, name: 'Washing machine', category: 'laundry', mode: 'flexible', max_kw: 2, allow_simultaneous: false },
      { appliance_id: 1, name: 'Refrigerator', category: 'kitchen', mode: 'fixed', max_kw: 0.15, allow_simultaneous: true },
    ],
    notes: ['Demand is power in kW (how hard the connection is pushed at one moment), not energy in kWh.'],
  };
}

async function openPeak(limit: number | null = 2) {
  const backend = installFakeBackend({ household: { ...HOME, max_load_kw: limit ?? 5 }, energy: { peak: (weekday) => analysis(weekday, limit) } });
  renderApp('/peak-load');
  await screen.findByRole('heading', { level: 1, name: 'Peak Load' });
  return backend;
}

describe('Peak Load page', () => {
  it('opens on the worst day and shows the headline figures', async () => {
    await openPeak();

    expect(await screen.findByText('Showing the day with the highest peak')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Mon' })).toHaveAttribute('aria-checked', 'true');
    const peakTile = screen.getByText('Peak demand (worst case)').parentElement as HTMLElement;
    expect(peakTile).toHaveTextContent('2.15 kW');
    expect(peakTile).toHaveTextContent('19:00–20:30 on Mon');
    expect(screen.getByText('Over by 0.15 kW')).toBeInTheDocument();
    expect(screen.getByText('Time over limit').parentElement).toHaveTextContent('90 min');
  });

  it('warns about load-limit violations with times and culprits', async () => {
    await openPeak();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Load limit exceeded on Mon (2 kW limit)');
    expect(alert).toHaveTextContent('19:00–20:30: up to 2.15 kW, 0.15 kW over. Running: Washing machine, Refrigerator.');
  });

  it('lists the peak contributors and conflicts', async () => {
    await openPeak();

    const peak = within((await screen.findByRole('heading', { name: 'At the peak' })).closest('section') as HTMLElement);
    expect(peak.getByRole('table')).toHaveTextContent('Washing machine');
    expect(peak.getByRole('img', { name: '93% of peak' })).toBeInTheDocument();

    const conflicts = within(screen.getByRole('heading', { name: 'Not allowed together' }).closest('section') as HTMLElement);
    expect(conflicts.getByText('Washing machine, Dishwasher')).toBeInTheDocument();
    expect(conflicts.getByText('20:00–20:30')).toBeInTheDocument();
  });

  it('switches to another day', async () => {
    const backend = await openPeak();
    await screen.findByText('Over by 0.15 kW');

    await userEvent.click(screen.getByRole('radio', { name: 'Tue' }));

    await waitFor(() => expect(backend.requests.at(-1)?.path).toBe('/api/peak-load/analysis?weekday=1'));
    expect(await screen.findByText('None')).toBeInTheDocument(); // time over limit
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText('Showing the day with the highest peak')).not.toBeInTheDocument();
  });

  it('offers the hourly data as a table', async () => {
    await openPeak();
    const card = (await screen.findByRole('heading', { name: '24-hour load profile' })).closest('section') as HTMLElement;

    await userEvent.click(within(card).getByText('Show data table'));

    const table = within(card).getByRole('table', { name: 'Highest demand in each hour' });
    expect(within(table).getByText('19:00–20:00')).toBeInTheDocument();
    expect(within(table).getAllByText('2.15 kW').length).toBeGreaterThan(0);
  });

  it('asks for a load limit when none is set', async () => {
    await openPeak(null);

    expect(await screen.findByText(/No household load limit is set/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Set load limit' })).toHaveAttribute('href', '/settings');
  });
});
