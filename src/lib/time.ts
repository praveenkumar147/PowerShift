/**
 * Times of day are "minutes since midnight", as in the backend
 * (backend/powershift/domain/time_window.py). Start times are 0-1439; end times are
 * 1-1440, where 1440 means midnight at the END of the day.
 */

export type TimeFormat = '12h' | '24h';

export const MINUTES_PER_DAY = 1440;
export const TIME_STEP_MINUTES = 15;

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

/** 1320 -> "22:00" or "10:00 PM". 1440 -> "24:00" or "12:00 AM". */
export function formatMinute(minute: number, format: TimeFormat = '24h'): string {
  const hours = Math.floor(minute / 60);
  const mins = minute % 60;
  if (format === '24h') return `${pad(hours)}:${pad(mins)}`;
  const h12 = hours % 12 === 0 ? 12 : hours % 12;
  const suffix = hours % 24 < 12 ? 'AM' : 'PM';
  return `${h12}:${pad(mins)} ${suffix}`;
}

export function formatWindow(start: number, end: number, format: TimeFormat = '24h'): string {
  return `${formatMinute(start, format)}–${formatMinute(end, format)}`;
}

/** 90 -> "1 h 30 min", 60 -> "1 h", 45 -> "45 min" */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours && mins) return `${hours} h ${mins} min`;
  return hours ? `${hours} h` : `${mins} min`;
}

/** Value for <input type="time">. End-of-day 1440 shows as "00:00". */
export function toTimeInput(minute: number): string {
  return formatMinute(minute % MINUTES_PER_DAY, '24h');
}

/** "HH:MM" -> minutes, or null if empty/invalid. */
export function parseTimeInput(value: string): number | null {
  const match = /^(\d{2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const hours = Number(match[1]);
  const mins = Number(match[2]);
  if (hours > 23 || mins > 59) return null;
  return hours * 60 + mins;
}

/** Like parseTimeInput, but "00:00" as an END time means midnight at the end of the day. */
export function parseEndTimeInput(value: string): number | null {
  const minute = parseTimeInput(value);
  return minute === 0 ? MINUTES_PER_DAY : minute;
}
