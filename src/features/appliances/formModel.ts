/**
 * Form state <-> API payload.
 *
 * Inputs hold strings ("1500", "22:00") so the user can type freely. This module
 * converts them to the API shape and reports values that can't be parsed. Every
 * error key uses the same field path as the backend (e.g. "flexible.current_start_minute")
 * so client-side and server-side errors appear in the same place.
 */
import {
  ALL_DAYS,
  type Appliance,
  type ApplianceCategory,
  type ApplianceInput,
  type ApplianceMode,
  type FlexibleSettings,
  type Priority,
} from '@/features/appliances/types';
import { parseEndTimeInput, parseTimeInput, toTimeInput } from '@/lib/time';

export interface BlockValues {
  start: string;
  end: string;
}

export interface ApplianceFormValues {
  name: string;
  category: ApplianceCategory;
  ratedPowerW: string;
  quantity: string;
  dutyCyclePercent: string;
  mode: ApplianceMode;
  priority: Priority;
  allowSimultaneous: boolean;
  operatingDays: number[];
  fixedBlocks: BlockValues[];
  durationHours: string;
  durationMinutes: string;
  earliestStart: string;
  latestEnd: string;
  currentStart: string;
  usePreferredWindow: boolean;
  preferredStart: string;
  preferredEnd: string;
  mustBeContiguous: boolean;
}

export type FieldErrors = Record<string, string>;

export const ALL_DAY_BLOCK: BlockValues = { start: '00:00', end: '00:00' };

export function emptyFormValues(): ApplianceFormValues {
  return {
    name: '',
    category: 'other',
    ratedPowerW: '',
    quantity: '1',
    dutyCyclePercent: '100',
    mode: 'fixed',
    priority: 'medium',
    allowSimultaneous: true,
    operatingDays: [...ALL_DAYS],
    fixedBlocks: [{ ...ALL_DAY_BLOCK }],
    durationHours: '1',
    durationMinutes: '0',
    earliestStart: '00:00',
    latestEnd: '00:00',
    currentStart: '',
    usePreferredWindow: false,
    preferredStart: '',
    preferredEnd: '',
    mustBeContiguous: true,
  };
}

export function fromAppliance(appliance: Appliance): ApplianceFormValues {
  const base = emptyFormValues();
  const flex = appliance.flexible;
  return {
    ...base,
    name: appliance.name,
    category: appliance.category,
    ratedPowerW: String(appliance.rated_power_w),
    quantity: String(appliance.quantity),
    dutyCyclePercent: String(Math.round(appliance.duty_cycle * 1000) / 10),
    mode: appliance.mode,
    priority: appliance.priority,
    allowSimultaneous: appliance.allow_simultaneous,
    operatingDays: [...appliance.operating_days],
    fixedBlocks: appliance.fixed_blocks.length
      ? appliance.fixed_blocks.map((b) => ({ start: toTimeInput(b.start_minute), end: toTimeInput(b.end_minute) }))
      : base.fixedBlocks,
    ...(flex && {
      durationHours: String(Math.floor(flex.run_duration_minutes / 60)),
      durationMinutes: String(flex.run_duration_minutes % 60),
      earliestStart: toTimeInput(flex.earliest_start_minute),
      latestEnd: toTimeInput(flex.latest_end_minute),
      currentStart: toTimeInput(flex.current_start_minute),
      usePreferredWindow: flex.preferred_start_minute !== null,
      preferredStart: flex.preferred_start_minute !== null ? toTimeInput(flex.preferred_start_minute) : '',
      preferredEnd: flex.preferred_end_minute !== null ? toTimeInput(flex.preferred_end_minute) : '',
      mustBeContiguous: flex.must_be_contiguous,
    }),
  };
}

const TIME_REQUIRED = 'Enter a time.';

function parseNumber(value: string, errors: FieldErrors, key: string, message: string): number {
  const parsed = Number(value);
  if (value.trim() === '' || Number.isNaN(parsed)) errors[key] = message;
  return parsed;
}

function parseTime(value: string, errors: FieldErrors, key: string, isEnd = false): number {
  const parsed = isEnd ? parseEndTimeInput(value) : parseTimeInput(value);
  if (parsed === null) errors[key] = TIME_REQUIRED;
  return parsed ?? 0;
}

function toFlexible(values: ApplianceFormValues, errors: FieldErrors): FlexibleSettings {
  const p = 'flexible.';
  const usePreferred = values.usePreferredWindow;
  return {
    run_duration_minutes: Number(values.durationHours) * 60 + Number(values.durationMinutes),
    earliest_start_minute: parseTime(values.earliestStart, errors, `${p}earliest_start_minute`),
    latest_end_minute: parseTime(values.latestEnd, errors, `${p}latest_end_minute`, true),
    current_start_minute: parseTime(values.currentStart, errors, `${p}current_start_minute`),
    preferred_start_minute: usePreferred ? parseTime(values.preferredStart, errors, `${p}preferred_start_minute`) : null,
    preferred_end_minute: usePreferred ? parseTime(values.preferredEnd, errors, `${p}preferred_end_minute`, true) : null,
    must_be_contiguous: values.mustBeContiguous,
  };
}

export function toApplianceInput(values: ApplianceFormValues): { input: ApplianceInput } | { errors: FieldErrors } {
  const errors: FieldErrors = {};
  if (!values.name.trim()) errors.name = 'Enter a name.';
  const ratedPower = parseNumber(values.ratedPowerW, errors, 'rated_power_w', 'Enter the rated power in watts.');
  const quantity = parseNumber(values.quantity, errors, 'quantity', 'Enter how many units.');
  const dutyPercent = parseNumber(values.dutyCyclePercent, errors, 'duty_cycle', 'Enter a percentage.');
  if (values.operatingDays.length === 0) errors.operating_days = 'Select at least one day.';

  const isFixed = values.mode === 'fixed';
  const fixedBlocks = isFixed
    ? values.fixedBlocks.map((block, i) => ({
        start_minute: parseTime(block.start, errors, `fixed_blocks.${i}.start_minute`),
        end_minute: parseTime(block.end, errors, `fixed_blocks.${i}.end_minute`, true),
      }))
    : [];
  const flexible = isFixed ? null : toFlexible(values, errors);

  if (Object.keys(errors).length) return { errors };

  return {
    input: {
      name: values.name.trim(),
      category: values.category,
      rated_power_w: ratedPower,
      quantity,
      duty_cycle: dutyPercent / 100,
      mode: values.mode,
      priority: values.priority,
      allow_simultaneous: values.allowSimultaneous,
      operating_days: [...values.operatingDays].sort((a, b) => a - b),
      fixed_blocks: fixedBlocks,
      flexible,
    },
  };
}
