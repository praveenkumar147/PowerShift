/** Mirrors backend/powershift/schemas/peak_load.py. All power values are kW. */
import type { ApplianceCategory, ApplianceMode } from '@/features/appliances/types';

export interface ApplianceRef {
  appliance_id: number;
  name: string;
}

export interface ApplianceInfo extends ApplianceRef {
  category: ApplianceCategory;
  mode: ApplianceMode;
  max_kw: number;
  allow_simultaneous: boolean;
}

export interface Contributor extends ApplianceRef {
  mode: ApplianceMode;
  kw: number;
}

export interface PeriodWindow {
  start_minute: number;
  end_minute: number;
  minutes: number;
}

export interface Episode extends PeriodWindow {
  max_kw: number;
  appliances: ApplianceRef[];
}

export interface DemandStep {
  start_minute: number;
  worst_kw: number;
  expected_kw: number;
  fixed_kw: number;
  flexible_kw: number;
  appliance_ids: number[];
}

export interface DaySummary {
  weekday: number;
  peak_kw: number;
  peak_expected_kw: number;
  peak_start_minute: number;
  minutes_over_limit: number;
}

export interface PeakLoadAnalysis {
  weekday: number;
  selected_automatically: boolean;
  load_limit_kw: number | null;
  peak_kw: number;
  peak_expected_kw: number;
  headroom_kw: number | null;
  minutes_over_limit: number;
  peak_windows: PeriodWindow[];
  peak_fixed_kw: number;
  peak_flexible_kw: number;
  peak_contributors: Contributor[];
  steps: DemandStep[];
  violations: Episode[];
  high_demand: Episode[];
  overlaps: Episode[];
  conflicts: Episode[];
  week: DaySummary[];
  appliances: ApplianceInfo[];
  notes: string[];
}
