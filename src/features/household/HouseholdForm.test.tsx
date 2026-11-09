import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Household } from '@/features/household/api';
import { installFakeBackend } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';

const HOME: Household = {
  name: 'Our flat',
  occupants: 3,
  location_label: null,
  max_load_kw: 4,
  currency_code: 'INR',
  time_format: '24h',
};

describe('Household profile', () => {
  it('saves a new household from an empty form', async () => {
    const backend = installFakeBackend();
    renderApp('/settings');

    await userEvent.type(await screen.findByLabelText('Household name'), 'Our flat');
    await userEvent.type(screen.getByLabelText('Number of occupants'), '3');
    await userEvent.type(screen.getByLabelText('Maximum household load (kW)'), '4.5');
    await userEvent.type(screen.getByLabelText('Currency code'), 'inr');
    await userEvent.selectOptions(screen.getByLabelText('Time format'), '12h');
    await userEvent.click(screen.getByRole('button', { name: 'Save household' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Saved');
    expect(backend.household).toEqual({
      name: 'Our flat',
      occupants: 3,
      location_label: null,
      max_load_kw: 4.5,
      currency_code: 'INR',
      time_format: '12h',
    });
  });

  it('pre-fills an existing household and reports server validation errors per field', async () => {
    const backend = installFakeBackend({ household: HOME });
    backend.respondOnce('PUT', '/api/household', 422, {
      error: { code: 'validation_error', message: 'Some values are invalid.', fields: { max_load_kw: 'Input should be less than or equal to 1000' } },
    });
    renderApp('/settings');

    expect(await screen.findByLabelText('Household name')).toHaveValue('Our flat');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(screen.getByLabelText('Maximum household load (kW)')).toHaveAttribute('aria-invalid', 'true'));
    expect(screen.getByText('Input should be less than or equal to 1000')).toBeInTheDocument();
  });

  it('requires the essential fields before sending', async () => {
    const backend = installFakeBackend();
    renderApp('/settings');

    await userEvent.click(await screen.findByRole('button', { name: 'Save household' }));

    expect(screen.getByText('Enter a name for the household.')).toBeInTheDocument();
    expect(screen.getByText('Enter a number in kW.')).toBeInTheDocument();
    expect(backend.requests.some((r) => r.method === 'PUT')).toBe(false);
  });
});
