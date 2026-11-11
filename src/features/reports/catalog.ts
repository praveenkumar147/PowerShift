/** The reports the backend can produce (backend/powershift/services/report_service.py). */

export type ReportKind =
  | 'daily_energy'
  | 'monthly_energy'
  | 'appliance_consumption'
  | 'bill_estimate'
  | 'peak_load'
  | 'optimization_comparison'
  | 'simulation_comparison';

export type ReportFormat = 'csv' | 'pdf';

/** The inputs a report accepts; the options form shows only these. */
export type ParamKind = 'range' | 'category' | 'year' | 'monthOfYear' | 'weekday' | 'run' | 'scenarios';

export interface ReportDefinition {
  kind: ReportKind;
  title: string;
  description: string;
  includes: string[];
  params: ParamKind[];
}

export const REPORTS: readonly ReportDefinition[] = [
  {
    kind: 'daily_energy',
    title: 'Daily energy report',
    description: 'Estimated energy and energy charge for each day in a date range.',
    includes: ['One row per day with weekday', 'Totals for the period', 'The tariff used'],
    params: ['range', 'category'],
  },
  {
    kind: 'monthly_energy',
    title: 'Monthly energy report',
    description: 'Estimated energy and bill for each month of a year.',
    includes: ['All 12 months with day counts', 'Whole-household monthly bill', 'The tariff used'],
    params: ['year', 'category'],
  },
  {
    kind: 'appliance_consumption',
    title: 'Appliance consumption report',
    description: 'Which appliances and categories use the most, with their share and cost.',
    includes: ['Energy, share and energy charge per appliance', 'The same by category'],
    params: ['range', 'category'],
  },
  {
    kind: 'bill_estimate',
    title: 'Electricity bill estimate',
    description: 'An itemised estimated bill for one month.',
    includes: ['Energy charge, fixed charges, extra charges and taxes', 'Effective price per kWh', 'Full tariff configuration'],
    params: ['monthOfYear'],
  },
  {
    kind: 'peak_load',
    title: 'Peak load report',
    description: 'Household power demand (kW) for one day, with load-limit violations.',
    includes: ['Peak, expected peak, headroom', 'Demand in each hour', 'Violations, high-demand periods, overlaps', 'Peak by weekday'],
    params: ['weekday'],
  },
  {
    kind: 'optimization_comparison',
    title: 'Optimization comparison report',
    description: 'A Smart Scheduler run: current schedule against the optimized one.',
    includes: ['Bill, peak and savings before and after', 'Recommended times with reasons', 'Independent validation results'],
    params: ['run'],
  },
  {
    kind: 'simulation_comparison',
    title: 'Simulation comparison report',
    description: 'Scenarios from the Simulation Lab compared with your current household.',
    includes: ['Energy, bill and peak for each scenario', 'What each scenario changes', 'Savings from scheduling'],
    params: ['scenarios'],
  },
];

export const FORMAT_HELP: Record<ReportFormat, string> = {
  csv: 'Opens in Excel or any spreadsheet. Best for further analysis.',
  pdf: 'A formatted document for reading or printing.',
};

/** What every report contains, however it is exported. */
export const EVERY_REPORT_STATES = [
  'The date it was generated',
  'Units in every column heading (kWh for energy, kW for demand)',
  'The tariff it depends on',
  'The assumptions behind the numbers',
  'A clear label that all figures are estimates, not measurements',
];
