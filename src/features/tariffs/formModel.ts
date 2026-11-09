/**
 * Tariff form state <-> API payload. Inputs are strings; error keys use backend
 * field paths (e.g. "tou_periods.1.rate_per_kwh") so client and server errors
 * appear in the same place.
 */
import type { ChargeKind, DayType, SlabMode, Tariff, TariffInput, TariffType } from '@/features/tariffs/types';
import { parseEndTimeInput, parseTimeInput, toTimeInput } from '@/lib/time';

export interface PeriodValues {
  dayType: DayType;
  start: string;
  end: string;
  rate: string;
}

export interface SlabValues {
  upTo: string;
  rate: string;
}

export interface ChargeValues {
  kind: ChargeKind;
  label: string;
  amount: string;
}

export interface TariffFormValues {
  name: string;
  tariffType: TariffType;
  effectiveDate: string;
  flatRate: string;
  periods: PeriodValues[];
  slabs: SlabValues[];
  slabMode: SlabMode;
  charges: ChargeValues[];
}

export type FieldErrors = Record<string, string>;

function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

export function emptyTariffValues(): TariffFormValues {
  return {
    name: '',
    tariffType: 'flat',
    effectiveDate: todayIso(),
    flatRate: '',
    periods: [{ dayType: 'all', start: '00:00', end: '00:00', rate: '' }],
    slabs: [
      { upTo: '100', rate: '' },
      { upTo: '', rate: '' },
    ],
    slabMode: 'telescopic',
    charges: [],
  };
}

export function fromTariff(tariff: Tariff): TariffFormValues {
  const empty = emptyTariffValues();
  return {
    name: tariff.name,
    tariffType: tariff.tariff_type,
    effectiveDate: tariff.effective_date,
    flatRate: tariff.flat_rate_per_kwh === null ? '' : String(tariff.flat_rate_per_kwh),
    periods: tariff.tou_periods.length
      ? tariff.tou_periods.map((p) => ({
          dayType: p.day_type,
          start: toTimeInput(p.start_minute),
          end: toTimeInput(p.end_minute),
          rate: String(p.rate_per_kwh),
        }))
      : empty.periods,
    slabs: tariff.slabs.length
      ? tariff.slabs.map((s) => ({ upTo: s.up_to_kwh === null ? '' : String(s.up_to_kwh), rate: String(s.rate_per_kwh) }))
      : empty.slabs,
    slabMode: tariff.slab_mode,
    charges: tariff.charges.map((c) => ({ kind: c.kind, label: c.label, amount: String(c.amount) })),
  };
}

function number(value: string, errors: FieldErrors, key: string): number {
  const parsed = Number(value);
  if (value.trim() === '' || Number.isNaN(parsed)) errors[key] = 'Enter a number.';
  return parsed;
}

function time(value: string, errors: FieldErrors, key: string, isEnd: boolean): number {
  const parsed = isEnd ? parseEndTimeInput(value) : parseTimeInput(value);
  if (parsed === null) errors[key] = 'Enter a time.';
  return parsed ?? 0;
}

export function toTariffInput(values: TariffFormValues): { input: TariffInput } | { errors: FieldErrors } {
  const errors: FieldErrors = {};
  if (!values.name.trim()) errors.name = 'Enter a name.';
  if (!values.effectiveDate) errors.effective_date = 'Choose a date.';
  const type = values.tariffType;

  const flatRate = type === 'flat' ? number(values.flatRate, errors, 'flat_rate_per_kwh') : null;
  const periods =
    type === 'tou'
      ? values.periods.map((p, i) => ({
          day_type: p.dayType,
          start_minute: time(p.start, errors, `tou_periods.${i}.start_minute`, false),
          end_minute: time(p.end, errors, `tou_periods.${i}.end_minute`, true),
          rate_per_kwh: number(p.rate, errors, `tou_periods.${i}.rate_per_kwh`),
        }))
      : [];
  const slabs =
    type === 'slab'
      ? values.slabs.map((s, i) => ({
          // An empty upper limit means "no limit" (only valid for the last slab; the backend checks).
          up_to_kwh: s.upTo.trim() === '' ? null : number(s.upTo, errors, `slabs.${i}.up_to_kwh`),
          rate_per_kwh: number(s.rate, errors, `slabs.${i}.rate_per_kwh`),
        }))
      : [];
  const charges = values.charges.map((c, i) => {
    if (!c.label.trim()) errors[`charges.${i}.label`] = 'Enter a label.';
    return { kind: c.kind, label: c.label.trim(), amount: number(c.amount, errors, `charges.${i}.amount`) };
  });

  if (Object.keys(errors).length) return { errors };
  return {
    input: {
      name: values.name.trim(),
      tariff_type: type,
      effective_date: values.effectiveDate,
      flat_rate_per_kwh: flatRate,
      tou_periods: periods,
      slabs,
      slab_mode: values.slabMode,
      charges,
    },
  };
}
