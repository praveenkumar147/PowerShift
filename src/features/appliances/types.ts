/** Mirrors backend/powershift/schemas/appliance.py */

export type ApplianceCategory =
  | 'cooling'
  | 'lighting'
  | 'kitchen'
  | 'laundry'
  | 'entertainment'
  | 'water_heating'
  | 'electronics'
  | 'other';

export type ApplianceMode = 'fixed' | 'flexible';
export type Priority = 'low' | 'medium' | 'high';

export interface TimeBlock {
  start_minute: number;
  end_minute: number;
}

export interface FlexibleSettings {
  run_duration_minutes: number;
  earliest_start_minute: number;
  latest_end_minute: number;
  current_start_minute: number;
  preferred_start_minute: number | null;
  preferred_end_minute: number | null;
  must_be_contiguous: boolean;
}

export interface ApplianceInput {
  name: string;
  category: ApplianceCategory;
  rated_power_w: number;
  quantity: number;
  duty_cycle: number;
  mode: ApplianceMode;
  priority: Priority;
  allow_simultaneous: boolean;
  operating_days: number[];
  fixed_blocks: TimeBlock[];
  flexible: FlexibleSettings | null;
}

export interface ApplianceEstimates {
  max_power_kw: number;
  average_power_kw: number;
  on_hours_per_day: number;
  energy_per_operating_day_kwh: number;
  energy_per_week_kwh: number;
}

export interface Appliance extends ApplianceInput {
  id: number;
  estimates: ApplianceEstimates;
  warnings: string[];
}

export interface ApplianceFilters {
  search: string;
  category: ApplianceCategory | '';
  mode: ApplianceMode | '';
}

export const CATEGORY_LABELS: Record<ApplianceCategory, string> = {
  cooling: 'Cooling',
  lighting: 'Lighting',
  kitchen: 'Kitchen',
  laundry: 'Laundry',
  entertainment: 'Entertainment',
  water_heating: 'Water heating',
  electronics: 'Electronics',
  other: 'Other',
};

export const CATEGORIES = Object.keys(CATEGORY_LABELS) as ApplianceCategory[];

export const PRIORITY_LABELS: Record<Priority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
};

/** Index = weekday number used by the backend (0 = Monday). */
export const WEEKDAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;
export const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];
export const WEEKDAYS_ONLY = [0, 1, 2, 3, 4];
