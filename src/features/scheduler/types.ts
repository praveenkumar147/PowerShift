/** Mirrors backend/powershift/schemas/optimization.py */
import type { TariffSummary } from '@/features/energy/types';
import type { ApplianceInfo, DemandStep } from '@/features/peak-load/types';

export type Priority = 'cost' | 'peak' | 'balanced';
export type SolveStatus = 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'UNKNOWN' | 'MODEL_INVALID';
export type StartStep = 15 | 30 | 60;

export interface OptimizationRequest {
  priority: Priority;
  balance_weight: number;
  start_step_minutes: StartStep;
  time_limit_seconds: number;
}

export interface Reason {
  code: string;
  text: string;
}

export interface ScheduleItem {
  appliance_id: number;
  name: string;
  power_kw: number;
  duration_minutes: number;
  baseline_start_minute: number;
  start_minute: number;
  end_minute: number;
  moved: boolean;
  reasons: Reason[];
}

export interface ScheduleMetrics {
  weekly_energy_charge: number | null;
  monthly_bill: number | null;
  peak_kw: number;
  peak_expected_kw: number;
  peak_weekday: number;
  minutes_over_limit: number;
  conflict_minutes: number;
}

export interface ValidationCheck {
  code: string;
  label: string;
  passed: boolean;
  detail: string;
}

export interface SolverStage {
  name: string;
  status: string;
  value: number | null;
  seconds: number;
}

export interface Diagnostic {
  code: string;
  message: string;
}

export interface OptimizationRun {
  id: number;
  created_at: string;
  priority: Priority;
  balance_weight: number;
  start_step_minutes: number;
  time_limit_seconds: number;
  random_seed: number;
  solver: string;
  status: SolveStatus;
  proven_optimal: boolean;
  /** True only if a schedule was found AND every independent check passed. */
  schedule_valid: boolean;
  solve_time_ms: number;
  stages: SolverStage[];
  load_limit_kw: number | null;
  tariff: TariffSummary | null;
  bill_year: number;
  bill_month: number;
  baseline: ScheduleMetrics;
  optimized: ScheduleMetrics | null;
  /** Baseline bill minus optimized bill; negative = the new schedule costs more. */
  monthly_savings: number | null;
  peak_reduction_kw: number | null;
  items: ScheduleItem[];
  validation: ValidationCheck[];
  diagnostics: Diagnostic[];
  profile: { weekday: number; before: DemandStep[]; after: DemandStep[] } | null;
  appliances: ApplianceInfo[];
  notes: string[];
}

export interface OptimizationSummary {
  id: number;
  created_at: string;
  priority: Priority;
  status: SolveStatus;
  schedule_valid: boolean;
  solve_time_ms: number;
  moved_count: number;
  baseline_bill: number | null;
  optimized_bill: number | null;
  baseline_peak_kw: number;
  optimized_peak_kw: number | null;
}

export const PRIORITY_LABELS: Record<Priority, string> = {
  cost: 'Lowest cost',
  balanced: 'Balanced',
  peak: 'Lowest peak',
};

export const STAGE_LABELS: Record<string, string> = {
  cost: 'Minimise energy cost',
  peak: 'Minimise peak demand',
  balanced: 'Minimise weighted cost + peak',
  preferred_window: 'Keep runs in preferred windows',
  movement: 'Change usual times as little as possible',
};
