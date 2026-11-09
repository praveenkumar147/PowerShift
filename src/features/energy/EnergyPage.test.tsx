import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { BillEstimate, EnergyReport, HourlyProfile, MonthlyProjection } from '@/features/energy/types';
import { installFakeBackend, type EnergyFixtures } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };
const TARIFF = { id: 1, name: 'Test TOU', tariff_type: 'tou' as const };

const REPORT: EnergyReport = {
  start: '2026-11-01',
  end: '2026-11-30',
  days: 30,
  total_kwh: 62.7,
  average_daily_kwh: 2.09,
  energy_charge: 364.8,
  tariff: TARIFF,
  daily: [{ date: '2026-11-01', kwh: 1.44, energy_charge: 6.96 }],
  appliances: [
    { appliance_id: 1, name: 'Refrigerator', category: 'kitchen', mode: 'fixed', kwh: 43.2, share: 0.689, energy_charge: 208.8 },
    { appliance_id: 2, name: 'Washing machine', category: 'laundry', mode: 'flexible', kwh: 19.5, share: 0.311, energy_charge: 156 },
  ],
  categories: [
    { category: 'kitchen', kwh: 43.2, share: 0.689, energy_charge: 208.8 },
    { category: 'laundry', kwh: 19.5, share: 0.311, energy_charge: 156 },
  ],
  notes: ['Estimates from your appliance settings, not measured consumption.'],
};

const HOURLY: HourlyProfile = {
  weekday: null,
  hours: Array.from({ length: 24 }, (_, hour) => ({ hour, kwh: 0.06, fixed_kwh: 0.06, flexible_kwh: 0, price_per_kwh: 5 })),
  tariff: TARIFF,
  notes: [],
};

const MONTHLY: MonthlyProjection = {
  year: 2026,
  months: Array.from({ length: 12 }, (_, i) => ({ month: i + 1, days: 30, kwh: 60, bill_total: 400 })),
  tariff: TARIFF,
  notes: [],
};

const BILL: BillEstimate = {
  year: 2026,
  month: 11,
  days: 30,
  total_kwh: 62.7,
  tariff: TARIFF,
  lines: [
    { label: 'Energy charge', kind: 'energy', amount: 364.8, detail: '62.7 kWh priced by time of use' },
    { label: 'Electricity duty', kind: 'percentage', amount: 18.24, detail: '5% of subtotal' },
  ],
  subtotal: 364.8,
  total: 383.04,
  effective_rate_per_kwh: 6.109,
  notes: [],
};

async function openEnergy(energy: EnergyFixtures = { report: REPORT, hourly: HOURLY, monthly: MONTHLY, bill: BILL }) {
  const backend = installFakeBackend({ household: HOME, energy });
  renderApp('/energy');
  await screen.findByRole('heading', { level: 1, name: 'Energy Analysis' });
  return backend;
}

describe('Energy Analysis page', () => {
  it('shows headline figures from the report', async () => {
    await openEnergy();

    expect(await screen.findByText('62.7 kWh')).toBeInTheDocument();
    expect(screen.getByText('2.09 kWh')).toBeInTheDocument();
    const chargeTile = screen.getByText('Excludes fixed charges and taxes').parentElement as HTMLElement;
    expect(chargeTile).toHaveTextContent('₹364.80');
    expect(screen.getByText('68.9% of energy')).toBeInTheDocument();
  });

  it('offers data tables for the charts', async () => {
    await openEnergy();
    const appliances = (await screen.findByRole('heading', { name: 'By appliance' })).closest('section') as HTMLElement;

    await userEvent.click(within(appliances).getByText('Show data table'));

    const table = within(appliances).getByRole('table', { name: 'Energy by appliance' });
    expect(within(table).getByText('Washing machine')).toBeInTheDocument();
    expect(within(table).getByText('₹156.00')).toBeInTheDocument();
  });

  it('shows the itemised bill estimate', async () => {
    await openEnergy();

    const bill = within(await screen.findByRole('table', { name: /Estimated bill for/ }));
    expect(bill.getByText('Electricity duty')).toBeInTheDocument();
    expect(bill.getByText('₹383.04')).toBeInTheDocument();
  });

  it('lists the calculation assumptions', async () => {
    await openEnergy();
    const notes = await screen.findByRole('region', { name: 'How these figures are calculated' });
    expect(notes).toHaveTextContent('not measured consumption');
  });

  it('sends the chosen filters to the API', async () => {
    const backend = await openEnergy();
    await screen.findByText('62.7 kWh');

    await userEvent.selectOptions(screen.getByLabelText('Category'), 'laundry');

    await waitFor(() =>
      expect(backend.requests.some((r) => r.path.startsWith('/api/energy/report?') && r.path.includes('category=laundry'))).toBe(true),
    );
  });

  it('says costs need a tariff when none is active', async () => {
    await openEnergy({ report: { ...REPORT, energy_charge: null, tariff: null }, hourly: HOURLY, monthly: MONTHLY, bill: { ...BILL, total: null, lines: [] } });

    expect(await screen.findByText('No tariff')).toBeInTheDocument();
    expect(screen.getByText('Add a tariff to see costs')).toBeInTheDocument();
  });

  it('shows a range error from the backend next to the dates', async () => {
    const backend = installFakeBackend({ household: HOME, energy: { hourly: HOURLY, monthly: MONTHLY, bill: BILL } });
    backend.respondOnce('GET', '/api/energy/report', 422, {
      error: { code: 'validation_error', message: 'Choose a range of at most 366 days.', fields: { end: 'Choose a range of at most 366 days.' } },
    });
    renderApp('/energy');

    expect(await screen.findByText('Choose a range of at most 366 days.')).toBeInTheDocument();
    expect(screen.getByLabelText('From')).toHaveAttribute('aria-invalid', 'true');
  });
});
