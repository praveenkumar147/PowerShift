import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Appliance } from '@/features/appliances/types';
import { installFakeBackend, ZERO_ESTIMATES } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const FRIDGE: Appliance = {
  id: 1,
  name: 'Refrigerator',
  category: 'kitchen',
  rated_power_w: 150,
  quantity: 1,
  duty_cycle: 0.4,
  mode: 'fixed',
  priority: 'high',
  allow_simultaneous: true,
  operating_days: [0, 1, 2, 3, 4, 5, 6],
  fixed_blocks: [{ start_minute: 0, end_minute: 1440 }],
  flexible: null,
  estimates: { ...ZERO_ESTIMATES, average_power_kw: 0.06, energy_per_operating_day_kwh: 1.44 },
  warnings: [],
};

const WASHER: Appliance = {
  ...FRIDGE,
  id: 2,
  name: 'Washing machine',
  category: 'laundry',
  rated_power_w: 2000,
  duty_cycle: 0.5,
  mode: 'flexible',
  operating_days: [0, 3, 5],
  fixed_blocks: [],
  flexible: {
    run_duration_minutes: 90,
    earliest_start_minute: 1320,
    latest_end_minute: 360,
    current_start_minute: 1380,
    preferred_start_minute: null,
    preferred_end_minute: null,
    must_be_contiguous: true,
  },
  warnings: ['At full power this appliance draws 2.00 kW, more than the household load limit of 1.50 kW.'],
};

async function openAppliances(appliances: Appliance[] = []) {
  const backend = installFakeBackend({ appliances: structuredClone(appliances) });
  renderApp('/appliances');
  await screen.findByRole('heading', { level: 1, name: 'Appliances' });
  return backend;
}

function dialog() {
  return within(screen.getByRole('dialog'));
}

describe('Appliances page', () => {
  it('shows a helpful empty state that opens the add form', async () => {
    await openAppliances();

    await userEvent.click(await screen.findByRole('button', { name: 'Add your first appliance' }));

    expect(screen.getByRole('dialog', { name: 'Add appliance' })).toBeInTheDocument();
  });

  it('lists appliances with readable usage, days, estimates and warnings', async () => {
    await openAppliances([FRIDGE, WASHER]);

    const rows = await screen.findAllByRole('row');
    expect(rows).toHaveLength(3); // header + 2
    const fridgeRow = within(rows[1] as HTMLElement);
    expect(fridgeRow.getByText('All day')).toBeInTheDocument();
    expect(fridgeRow.getByText('Every day')).toBeInTheDocument();
    expect(fridgeRow.getByText('1.44 kWh')).toBeInTheDocument();
    expect(fridgeRow.getByText('avg 60 W at 40% duty')).toBeInTheDocument();

    const washerRow = within(rows[2] as HTMLElement);
    expect(washerRow.getByText('1 h 30 min within 22:00–06:00')).toBeInTheDocument();
    expect(washerRow.getByText('Mon, Thu, Sat')).toBeInTheDocument();
    expect(washerRow.getByText(/more than the household load limit/)).toBeInTheDocument();
  });

  it('creates a fixed appliance and shows it in the list', async () => {
    const backend = await openAppliances();
    await userEvent.click(screen.getByRole('button', { name: 'Add appliance' }));

    await userEvent.type(dialog().getByLabelText('Name'), 'Wi-Fi router');
    await userEvent.selectOptions(dialog().getByLabelText('Category'), 'electronics');
    await userEvent.type(dialog().getByLabelText('Rated power (W)'), '12');
    await userEvent.click(dialog().getByRole('button', { name: 'Add appliance' }));

    expect(await screen.findByText('Wi-Fi router')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    const post = backend.requests.find((r) => r.method === 'POST');
    expect(post?.body).toMatchObject({
      name: 'Wi-Fi router',
      category: 'electronics',
      rated_power_w: 12,
      duty_cycle: 1,
      mode: 'fixed',
      fixed_blocks: [{ start_minute: 0, end_minute: 1440 }],
      flexible: null,
    });
  });

  it('creates a flexible appliance with an overnight window', async () => {
    const backend = await openAppliances();
    await userEvent.click(screen.getByRole('button', { name: 'Add appliance' }));

    await userEvent.type(dialog().getByLabelText('Name'), 'Dishwasher');
    await userEvent.type(dialog().getByLabelText('Rated power (W)'), '1800');
    await userEvent.click(dialog().getByRole('radio', { name: 'Flexible' }));
    await userEvent.selectOptions(dialog().getByLabelText('Hours'), '2');
    await userEvent.selectOptions(dialog().getByLabelText('Minutes'), '30');
    fireEvent.change(dialog().getByLabelText('Earliest start'), { target: { value: '22:00' } });
    fireEvent.change(dialog().getByLabelText('Latest finish'), { target: { value: '06:00' } });
    fireEvent.change(dialog().getByLabelText('Usual start today'), { target: { value: '21:00' } });
    await userEvent.click(dialog().getByRole('button', { name: 'Add appliance' }));

    await waitFor(() => expect(backend.requests.some((r) => r.method === 'POST')).toBe(true));
    expect(backend.requests.find((r) => r.method === 'POST')?.body).toMatchObject({
      mode: 'flexible',
      fixed_blocks: [],
      flexible: {
        run_duration_minutes: 150,
        earliest_start_minute: 1320,
        latest_end_minute: 360,
        current_start_minute: 1260,
        preferred_start_minute: null,
      },
    });
  });

  it('blocks submission and explains missing values without calling the backend', async () => {
    const backend = await openAppliances();
    await userEvent.click(screen.getByRole('button', { name: 'Add appliance' }));

    await userEvent.click(dialog().getByRole('button', { name: 'Add appliance' }));

    expect(dialog().getByText('Enter a name.')).toBeInTheDocument();
    expect(dialog().getByText('Enter the rated power in watts.')).toBeInTheDocument();
    expect(dialog().getByLabelText('Name')).toHaveAttribute('aria-invalid', 'true');
    expect(backend.requests.some((r) => r.method === 'POST')).toBe(false);
  });

  it('shows backend rule errors next to the field they concern', async () => {
    const backend = await openAppliances([WASHER]);
    backend.respondOnce('PUT', '/api/appliances/2', 422, {
      error: {
        code: 'validation_error',
        message: 'Some values are inconsistent.',
        fields: { 'flexible.current_start_minute': 'Starting at this time, the run would not finish inside the allowed window.' },
      },
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Edit Washing machine' }));
    await userEvent.click(dialog().getByRole('button', { name: 'Save changes' }));

    expect(await dialog().findByText(/the run would not finish inside the allowed window/)).toBeInTheDocument();
    expect(dialog().getByLabelText('Usual start today')).toHaveAttribute('aria-invalid', 'true');
    expect(dialog().getByRole('alert')).toHaveTextContent('Some values need attention.');
  });

  it('shows a duplicate-name conflict clearly', async () => {
    const backend = await openAppliances([FRIDGE]);
    backend.respondOnce('POST', '/api/appliances', 409, {
      error: { code: 'conflict', message: 'An appliance named "Refrigerator" already exists.', fields: { name: 'This name is already used by another appliance.' } },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Add appliance' }));
    await userEvent.type(dialog().getByLabelText('Name'), 'Refrigerator');
    await userEvent.type(dialog().getByLabelText('Rated power (W)'), '150');

    await userEvent.click(dialog().getByRole('button', { name: 'Add appliance' }));

    expect(await dialog().findByText('An appliance named "Refrigerator" already exists.')).toBeInTheDocument();
    expect(dialog().getByText('This name is already used by another appliance.')).toBeInTheDocument();
  });

  it('edits an appliance with its current values pre-filled', async () => {
    const backend = await openAppliances([FRIDGE]);

    await userEvent.click(await screen.findByRole('button', { name: 'Edit Refrigerator' }));
    expect(dialog().getByLabelText('Duty cycle (%)')).toHaveValue(40);
    await userEvent.clear(dialog().getByLabelText('Quantity'));
    await userEvent.type(dialog().getByLabelText('Quantity'), '2');
    await userEvent.click(dialog().getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const put = backend.requests.find((r) => r.method === 'PUT');
    expect(put?.path).toBe('/api/appliances/1');
    expect(put?.body).toMatchObject({ quantity: 2, duty_cycle: 0.4 });
  });

  it('deletes only after confirmation', async () => {
    const backend = await openAppliances([FRIDGE, WASHER]);

    await userEvent.click(await screen.findByRole('button', { name: 'Delete Refrigerator' }));
    expect(dialog().getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await userEvent.click(dialog().getByRole('button', { name: 'Cancel' }));
    expect(backend.requests.some((r) => r.method === 'DELETE')).toBe(false);

    await userEvent.click(screen.getByRole('button', { name: 'Delete Refrigerator' }));
    await userEvent.click(dialog().getByRole('button', { name: 'Delete appliance' }));

    await waitFor(() => expect(screen.queryByText('Refrigerator')).not.toBeInTheDocument());
    expect(screen.getByText('Washing machine')).toBeInTheDocument();
  });

  it('closes the form with Escape', async () => {
    await openAppliances();
    await userEvent.click(screen.getByRole('button', { name: 'Add appliance' }));

    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('searches and filters through the API and can clear filters', async () => {
    const backend = await openAppliances([FRIDGE, WASHER]);
    await screen.findByText('Refrigerator');

    await userEvent.selectOptions(screen.getByLabelText('Filter by type'), 'flexible');
    await waitFor(() => expect(screen.queryByText('Refrigerator')).not.toBeInTheDocument());
    expect(backend.requests.at(-1)?.path).toBe('/api/appliances?mode=flexible');

    await userEvent.type(screen.getByLabelText('Search appliances'), 'zzz');
    expect(await screen.findByText('No matching appliances')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(await screen.findByText('Refrigerator')).toBeInTheDocument();
  });
});
