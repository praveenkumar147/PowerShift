import { describe, expect, it } from 'vitest';
import { emptyTariffValues, fromTariff, toTariffInput, type TariffFormValues } from '@/features/tariffs/formModel';
import type { Tariff } from '@/features/tariffs/types';

const TOU: Tariff = {
  id: 4,
  is_active: true,
  name: 'Night saver',
  tariff_type: 'tou',
  effective_date: '2026-04-01',
  flat_rate_per_kwh: null,
  tou_periods: [
    { day_type: 'all', start_minute: 1320, end_minute: 360, rate_per_kwh: 3 },
    { day_type: 'all', start_minute: 360, end_minute: 1320, rate_per_kwh: 7.25 },
  ],
  slabs: [],
  slab_mode: 'telescopic',
  charges: [{ kind: 'percentage', label: 'Duty', amount: 5 }],
};

function values(changes: Partial<TariffFormValues>): TariffFormValues {
  return { ...emptyTariffValues(), name: 'Home tariff', effectiveDate: '2026-01-01', ...changes };
}

describe('tariff form model', () => {
  it('builds a flat tariff and drops other types’ rows', () => {
    const result = toTariffInput(values({ flatRate: '6.5' }));
    expect(result).toEqual({
      input: {
        name: 'Home tariff',
        tariff_type: 'flat',
        effective_date: '2026-01-01',
        flat_rate_per_kwh: 6.5,
        tou_periods: [],
        slabs: [],
        slab_mode: 'telescopic',
        charges: [],
      },
    });
  });

  it('round-trips a time-of-use tariff with an overnight period', () => {
    const form = fromTariff(TOU);
    expect(form.periods[0]).toEqual({ dayType: 'all', start: '22:00', end: '06:00', rate: '3' });

    const result = toTariffInput(form);
    if (!('input' in result)) throw new Error('expected valid input');
    expect(result.input.tou_periods).toEqual(TOU.tou_periods);
    expect(result.input.charges).toEqual(TOU.charges);
  });

  it('treats an empty slab limit as "no limit"', () => {
    const result = toTariffInput(
      values({ tariffType: 'slab', slabs: [{ upTo: '100', rate: '3' }, { upTo: '', rate: '5' }] }),
    );
    expect('input' in result && result.input.slabs).toEqual([
      { up_to_kwh: 100, rate_per_kwh: 3 },
      { up_to_kwh: null, rate_per_kwh: 5 },
    ]);
  });

  it('reports unparseable values with backend field paths', () => {
    const result = toTariffInput(
      values({
        name: '',
        tariffType: 'tou',
        periods: [{ dayType: 'all', start: '', end: '00:00', rate: 'x' }],
        charges: [{ kind: 'fixed_monthly', label: '', amount: '50' }],
      }),
    );
    expect(result).toEqual({
      errors: {
        name: 'Enter a name.',
        'tou_periods.0.start_minute': 'Enter a time.',
        'tou_periods.0.rate_per_kwh': 'Enter a number.',
        'charges.0.label': 'Enter a label.',
      },
    });
  });
});
