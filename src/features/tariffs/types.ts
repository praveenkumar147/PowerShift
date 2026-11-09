/** Mirrors backend/powershift/schemas/tariff.py */

export type TariffType = 'flat' | 'tou' | 'slab';
export type DayType = 'all' | 'weekday' | 'weekend';
export type SlabMode = 'telescopic' | 'whole_usage';
export type ChargeKind = 'fixed_monthly' | 'per_kwh' | 'percentage';

export interface TouPeriod {
  day_type: DayType;
  start_minute: number;
  end_minute: number;
  rate_per_kwh: number;
}

export interface Slab {
  up_to_kwh: number | null;
  rate_per_kwh: number;
}

export interface Charge {
  kind: ChargeKind;
  label: string;
  amount: number;
}

export interface TariffInput {
  name: string;
  tariff_type: TariffType;
  effective_date: string;
  flat_rate_per_kwh: number | null;
  tou_periods: TouPeriod[];
  slabs: Slab[];
  slab_mode: SlabMode;
  charges: Charge[];
}

export interface Tariff extends TariffInput {
  id: number;
  is_active: boolean;
}

export const TARIFF_TYPE_LABELS: Record<TariffType, string> = {
  flat: 'Flat rate',
  tou: 'Time of use',
  slab: 'Slab-based',
};

export const DAY_TYPE_LABELS: Record<DayType, string> = {
  all: 'Every day',
  weekday: 'Weekdays (Mon–Fri)',
  weekend: 'Weekends (Sat–Sun)',
};

export const CHARGE_KIND_LABELS: Record<ChargeKind, string> = {
  fixed_monthly: 'Fixed per month',
  per_kwh: 'Extra per kWh',
  percentage: 'Percentage (tax / duty)',
};

export const SLAB_MODE_LABELS: Record<SlabMode, string> = {
  telescopic: 'Each slab at its own rate',
  whole_usage: 'All units at the highest slab reached',
};
