import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Tariff } from '@/features/tariffs/types';
import { installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

const FLAT: Tariff = {
  id: 1,
  is_active: true,
  name: 'Domestic flat',
  tariff_type: 'flat',
  effective_date: '2026-04-01',
  flat_rate_per_kwh: 6.5,
  tou_periods: [],
  slabs: [],
  slab_mode: 'telescopic',
  charges: [{ kind: 'percentage', label: 'Electricity duty', amount: 5 }],
};

const SLAB: Tariff = {
  ...FLAT,
  id: 2,
  is_active: false,
  name: 'Slab plan',
  tariff_type: 'slab',
  flat_rate_per_kwh: null,
  slabs: [
    { up_to_kwh: 100, rate_per_kwh: 3 },
    { up_to_kwh: null, rate_per_kwh: 5.25 },
  ],
  charges: [],
};

async function openTariffs(tariffs: Tariff[] = []) {
  const backend = installFakeBackend({ household: HOME, tariffs: structuredClone(tariffs) });
  renderApp('/tariff');
  await screen.findByRole('heading', { level: 1, name: 'Electricity Tariff' });
  return backend;
}

const dialog = () => within(screen.getByRole('dialog'));

describe('Tariff page', () => {
  it('explains that rates are never assumed when there is no tariff', async () => {
    await openTariffs();
    expect(await screen.findByText(/never assumes rates from your location/)).toBeInTheDocument();
  });

  it('shows each tariff with its rates in the household currency', async () => {
    await openTariffs([FLAT, SLAB]);

    const flat = within(await screen.findByRole('article', { name: 'Domestic flat' }));
    expect(flat.getByText('Active')).toBeInTheDocument();
    expect(flat.getByText('₹6.50/kWh')).toBeInTheDocument();
    expect(flat.getByText('5%')).toBeInTheDocument();

    const slab = within(screen.getByRole('article', { name: 'Slab plan' }));
    expect(slab.getByText('0–100 kWh')).toBeInTheDocument();
    expect(slab.getByText('Above 100 kWh')).toBeInTheDocument();
    expect(slab.getByText('₹5.25/kWh')).toBeInTheDocument();
  });

  it('creates a flat tariff with a fixed charge', async () => {
    const backend = await openTariffs();
    await userEvent.click(screen.getByRole('button', { name: 'Add tariff' }));

    await userEvent.type(dialog().getByLabelText('Name'), 'My tariff');
    await userEvent.type(dialog().getByLabelText('Price (INR/kWh)'), '7.1');
    await userEvent.click(dialog().getByRole('button', { name: 'Add charge' }));
    await userEvent.type(dialog().getByLabelText('Label'), 'Meter rent');
    await userEvent.type(dialog().getByLabelText('Amount (INR per month)'), '40');
    await userEvent.click(dialog().getByRole('button', { name: 'Add tariff' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(backend.requests.find((r) => r.method === 'POST')?.body).toMatchObject({
      name: 'My tariff',
      tariff_type: 'flat',
      flat_rate_per_kwh: 7.1,
      tou_periods: [],
      charges: [{ kind: 'fixed_monthly', label: 'Meter rent', amount: 40 }],
    });
    expect(await screen.findByRole('article', { name: 'My tariff' })).toBeInTheDocument();
  });

  it('builds a time-of-use tariff and shows the backend coverage error', async () => {
    const backend = await openTariffs();
    backend.respondOnce('POST', '/api/tariffs', 422, {
      error: { code: 'validation_error', message: 'Some tariff values are inconsistent.', fields: { tou_periods: 'No price is set for 18:00.' } },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Add tariff' }));
    await userEvent.type(dialog().getByLabelText('Name'), 'Night saver');
    await userEvent.click(dialog().getByRole('radio', { name: 'Time of use' }));
    fireEvent.change(dialog().getByLabelText('Until'), { target: { value: '18:00' } });
    await userEvent.type(dialog().getByLabelText('Rate (INR/kWh)'), '4');

    await userEvent.click(dialog().getByRole('button', { name: 'Add tariff' }));

    expect(await dialog().findByText('No price is set for 18:00.')).toBeInTheDocument();
    expect(backend.requests.find((r) => r.method === 'POST')?.body).toMatchObject({
      tariff_type: 'tou',
      flat_rate_per_kwh: null,
      tou_periods: [{ day_type: 'all', start_minute: 0, end_minute: 1080, rate_per_kwh: 4 }],
    });
  });

  it('switches the active tariff', async () => {
    const backend = await openTariffs([FLAT, SLAB]);

    await userEvent.click(await screen.findByRole('button', { name: 'Use this tariff' }));

    await waitFor(() => expect(backend.requests.some((r) => r.path === '/api/tariffs/2/activate')).toBe(true));
    const slab = within(await screen.findByRole('article', { name: 'Slab plan' }));
    expect(await slab.findByText('Active')).toBeInTheDocument();
  });

  it('warns before deleting the active tariff', async () => {
    await openTariffs([FLAT]);

    await userEvent.click(await screen.findByRole('button', { name: 'Delete Domestic flat' }));

    expect(dialog().getByText(/This is your active tariff/)).toBeInTheDocument();
    await userEvent.click(dialog().getByRole('button', { name: 'Delete tariff' }));
    expect(await screen.findByText('No tariff yet')).toBeInTheDocument();
  });
});
