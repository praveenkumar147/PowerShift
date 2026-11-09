/** Human-readable summaries of appliance settings for the list view. */
import { ALL_DAYS, WEEKDAYS_ONLY, WEEKDAY_SHORT, type Appliance } from '@/features/appliances/types';
import { formatDuration, formatWindow, type TimeFormat } from '@/lib/time';

function sameDays(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((day, i) => day === b[i]);
}

export function describeDays(days: number[]): string {
  if (sameDays(days, ALL_DAYS)) return 'Every day';
  if (sameDays(days, WEEKDAYS_ONLY)) return 'Weekdays';
  if (sameDays(days, [5, 6])) return 'Weekends';
  return days.map((d) => WEEKDAY_SHORT[d]).join(', ');
}

export function describeUsage(appliance: Appliance, format: TimeFormat): string {
  if (appliance.mode === 'fixed') {
    const [only] = appliance.fixed_blocks;
    if (appliance.fixed_blocks.length === 1 && only && only.start_minute === 0 && only.end_minute === 1440) {
      return 'All day';
    }
    return appliance.fixed_blocks.map((b) => formatWindow(b.start_minute, b.end_minute, format)).join(', ');
  }
  const flex = appliance.flexible;
  if (!flex) return '';
  return `${formatDuration(flex.run_duration_minutes)} within ${formatWindow(flex.earliest_start_minute, flex.latest_end_minute, format)}`;
}
