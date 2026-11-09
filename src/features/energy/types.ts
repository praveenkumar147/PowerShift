/** Mirrors backend/powershift/schemas/energy.py */
import type { ApplianceCategory, ApplianceMode } from '@/features/appliances/types';
import type { TariffType } from '@/features/tariffs/types';

export interface TariffSummary {
  id: number;
  name: string;
  tariff_type: TariffType;
}

export interface DayRow {
  date: string;
  kwh: number;
  energy_charge: number | null;
}

export interface ApplianceRow {
  appliance_id: number;
  name: string;
  category: ApplianceCategory;
  mode: ApplianceMode;
  kwh: number;
  share: number;
  energy_charge: number | null;
}

export interface CategoryRow {
  category: ApplianceCategory;
  kwh: number;
  share: number;
  energy_charge: number | null;
}

export interface EnergyReport {
  start: string;
  end: string;
  days: number;
  total_kwh: number;
  average_daily_kwh: number;
  energy_charge: number | null;
  tariff: TariffSummary | null;
  daily: DayRow[];
  appliances: ApplianceRow[];
  categories: CategoryRow[];
  notes: string[];
}

export interface HourRow {
  hour: number;
  kwh: number;
  fixed_kwh: number;
  flexible_kwh: number;
  price_per_kwh: number | null;
}

export interface HourlyProfile {
  weekday: number | null;
  hours: HourRow[];
  tariff: TariffSummary | null;
  notes: string[];
}

export interface MonthRow {
  month: number;
  days: number;
  kwh: number;
  bill_total: number | null;
}

export interface MonthlyProjection {
  year: number;
  months: MonthRow[];
  tariff: TariffSummary | null;
  notes: string[];
}

export interface BillLine {
  label: string;
  kind: string;
  amount: number;
  detail: string;
}

export interface BillEstimate {
  year: number;
  month: number;
  days: number;
  total_kwh: number;
  tariff: TariffSummary | null;
  lines: BillLine[];
  subtotal: number | null;
  total: number | null;
  effective_rate_per_kwh: number | null;
  notes: string[];
}

export interface EnergyFilters {
  start: string;
  end: string;
  category: ApplianceCategory | '';
}
