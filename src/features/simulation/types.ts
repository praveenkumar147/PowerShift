/** Mirrors backend/powershift/schemas/simulation.py */
import type { ApplianceInput } from '@/features/appliances/types';
import type { TariffSummary } from '@/features/energy/types';
import type { Diagnostic, Priority, ScheduleItem, SolveStatus, ValidationCheck } from '@/features/scheduler/types';

export type SimChange =
  | { type: 'add_appliance'; appliance: ApplianceInput }
  | { type: 'replace_appliance'; appliance_id: number; appliance: ApplianceInput }
  | { type: 'remove_appliance'; appliance_id: number }
  | { type: 'change_tariff'; tariff_id: number }
  | { type: 'set_load_limit'; max_load_kw: number };

export interface ScenarioInput {
  name: string;
  description: string | null;
  priority: Priority;
  balance_weight: number;
  changes: SimChange[];
}

export interface SimMetrics {
  monthly_kwh: number;
  monthly_bill: number | null;
  peak_kw: number;
  peak_expected_kw: number;
  minutes_over_limit: number;
  conflict_minutes: number;
}

export interface SimulationResult {
  id: number;
  scenario_id: number;
  scenario_name: string;
  created_at: string;
  priority: Priority;
  balance_weight: number;
  change_descriptions: string[];
  tariff: TariffSummary | null;
  load_limit_kw: number | null;
  bill_year: number;
  bill_month: number;
  /** Your actual household today; never modified by a scenario. */
  baseline: SimMetrics;
  /** The scenario at its usual times, before optimisation. */
  scenario: SimMetrics;
  optimized: SimMetrics | null;
  status: SolveStatus | null;
  proven_optimal: boolean;
  schedule_valid: boolean;
  solve_time_ms: number;
  optimization_note: string | null;
  kwh_change: number;
  /** Scenario bill minus current bill, before scheduling. Positive = costs more. */
  bill_change: number | null;
  /** Optimised scenario bill minus current bill. Negative = saves money overall. */
  optimized_bill_change: number | null;
  /** What scheduling alone recovers: scenario bill minus optimised bill. */
  optimization_savings: number | null;
  peak_change_kw: number;
  items: ScheduleItem[];
  validation: ValidationCheck[];
  diagnostics: Diagnostic[];
  notes: string[];
}

export interface Scenario extends ScenarioInput {
  id: number;
  change_descriptions: string[];
  created_at: string;
  updated_at: string;
  latest_result: SimulationResult | null;
  /** True if the scenario was edited after its latest result was produced. */
  result_is_stale: boolean;
}
