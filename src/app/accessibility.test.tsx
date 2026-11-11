import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { describe, expect, it } from 'vitest';
import { NAV_ITEMS } from '@/app/navigation';
import { installFakeBackend, ZERO_ESTIMATES } from '@/test/fakeBackend';
import { renderApp } from '@/test/render';
import type { Appliance } from '@/features/appliances/types';

const FRIDGE: Appliance = {
  id: 1, name: 'Refrigerator', category: 'kitchen', rated_power_w: 150, quantity: 1, duty_cycle: 0.4, mode: 'fixed', priority: 'high',
  allow_simultaneous: true, operating_days: [0, 1, 2, 3, 4, 5, 6], fixed_blocks: [{ start_minute: 0, end_minute: 1440 }], flexible: null,
  estimates: { ...ZERO_ESTIMATES, average_power_kw: 0.06, energy_per_operating_day_kwh: 1.44 }, warnings: [],
};
const HOME = { name: 'Home', occupants: 2, location_label: null, max_load_kw: 5, currency_code: 'INR', time_format: '24h' as const };

/** Structure, names, labels, roles and ARIA. (Colour contrast needs real layout; it is checked in the browser.) */
async function violationsOf(container: Element): Promise<string[]> {
  const result = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
  return result.violations.map((v) => `${v.id}: ${v.help} -> ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`);
}

describe('Accessibility (axe-core)', () => {
  it.each(NAV_ITEMS.map((item) => [item.label, item.path] as const))('%s page has no detectable violations', async (label, path) => {
    installFakeBackend({ household: HOME, appliances: [FRIDGE] });
    const { container } = renderApp(path);
    await screen.findByRole('heading', { level: 1, name: label === 'Overview' ? 'Overview' : label });
    await waitFor(() => expect(screen.queryByRole('status', { name: /Loading|Checking/ })).not.toBeInTheDocument());

    expect(await violationsOf(container)).toEqual([]);
  });

  it('actually reports problems (the check is not vacuous)', async () => {
    const host = document.createElement('div');
    host.innerHTML = '<button></button><img src="x.png"><input type="text">';
    document.body.append(host);
    const found = await violationsOf(host);
    host.remove();
    expect(found.join(' ')).toMatch(/button-name/);
    expect(found.join(' ')).toMatch(/image-alt/);
    expect(found.join(' ')).toMatch(/label/);
  });

  it('dialogs have no violations: the appliance form', async () => {
    installFakeBackend({ household: HOME, appliances: [FRIDGE] });
    renderApp('/appliances');
    await userEvent.click(await screen.findByRole('button', { name: /Add appliance/ }));
    const dialog = await screen.findByRole('dialog');
    expect(await violationsOf(dialog)).toEqual([]);
  });

  it('dialogs have no violations: reset confirmation', async () => {
    installFakeBackend({ household: HOME });
    renderApp('/settings');
    await userEvent.click(await screen.findByRole('button', { name: 'Delete all data…' }));
    const dialog = await screen.findByRole('dialog');
    expect(await violationsOf(dialog)).toEqual([]);
  });
});
