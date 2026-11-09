import { describe, expect, it } from 'vitest';
import { emptyFormValues, fromAppliance, toApplianceInput, type ApplianceFormValues } from '@/features/appliances/formModel';
import type { Appliance } from '@/features/appliances/types';

const WASHER: Appliance = {
  id: 3,
  name: 'Washing machine',
  category: 'laundry',
  rated_power_w: 2000,
  quantity: 1,
  duty_cycle: 0.5,
  mode: 'flexible',
  priority: 'medium',
  allow_simultaneous: false,
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
  estimates: { max_power_kw: 2, average_power_kw: 1, on_hours_per_day: 1.5, energy_per_operating_day_kwh: 1.5, energy_per_week_kwh: 4.5 },
  warnings: [],
};

function form(changes: Partial<ApplianceFormValues>): ApplianceFormValues {
  return { ...emptyFormValues(), name: 'Fridge', ratedPowerW: '150', ...changes };
}

describe('appliance form model', () => {
  it('converts a fixed appliance, with 00:00 as the end of the day and duty cycle as a fraction', () => {
    const result = toApplianceInput(form({ dutyCyclePercent: '40' }));

    expect(result).toEqual({
      input: expect.objectContaining({
        rated_power_w: 150,
        duty_cycle: 0.4,
        fixed_blocks: [{ start_minute: 0, end_minute: 1440 }],
        flexible: null,
      }),
    });
  });

  it('round-trips a flexible appliance with an overnight window', () => {
    const values = fromAppliance(WASHER);

    expect(values.earliestStart).toBe('22:00');
    expect(values.latestEnd).toBe('06:00');
    expect(values.durationHours).toBe('1');
    expect(values.durationMinutes).toBe('30');
    expect(values.dutyCyclePercent).toBe('50');

    const result = toApplianceInput(values);
    if (!('input' in result)) throw new Error('expected valid input');
    expect(result.input).toEqual({
      name: WASHER.name,
      category: WASHER.category,
      rated_power_w: WASHER.rated_power_w,
      quantity: WASHER.quantity,
      duty_cycle: WASHER.duty_cycle,
      mode: WASHER.mode,
      priority: WASHER.priority,
      allow_simultaneous: WASHER.allow_simultaneous,
      operating_days: WASHER.operating_days,
      fixed_blocks: WASHER.fixed_blocks,
      flexible: WASHER.flexible,
    });
  });

  it('drops fixed blocks for flexible appliances and flexible settings for fixed ones', () => {
    const flexible = toApplianceInput({ ...fromAppliance(WASHER), fixedBlocks: [{ start: '01:00', end: '02:00' }] });
    expect('input' in flexible && flexible.input.fixed_blocks).toEqual([]);

    const fixed = toApplianceInput({ ...fromAppliance(WASHER), mode: 'fixed' });
    expect('input' in fixed && fixed.input.flexible).toBeNull();
  });

  it('reports unparseable values using backend field paths', () => {
    const result = toApplianceInput(
      form({ name: ' ', ratedPowerW: 'abc', operatingDays: [], fixedBlocks: [{ start: '', end: '06:00' }] }),
    );

    expect(result).toEqual({
      errors: {
        name: 'Enter a name.',
        rated_power_w: 'Enter the rated power in watts.',
        operating_days: 'Select at least one day.',
        'fixed_blocks.0.start_minute': 'Enter a time.',
      },
    });
  });

  it('requires preferred times only when the preferred window is switched on', () => {
    const flexValues = { ...fromAppliance(WASHER), preferredStart: '', preferredEnd: '' };

    expect('input' in toApplianceInput(flexValues)).toBe(true);
    expect(toApplianceInput({ ...flexValues, usePreferredWindow: true })).toEqual({
      errors: {
        'flexible.preferred_start_minute': 'Enter a time.',
        'flexible.preferred_end_minute': 'Enter a time.',
      },
    });
  });
});
