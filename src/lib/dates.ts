/** Calendar helpers working with ISO dates ("2026-11-09") in local time. */

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

export function toIsoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Parses "YYYY-MM-DD" as a local date (new Date("2026-11-09") would be UTC midnight). */
export function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1);
}

export function monthRange(year: number, month: number): { start: string; end: string } {
  return { start: toIsoDate(new Date(year, month - 1, 1)), end: toIsoDate(new Date(year, month, 0)) };
}

export function yearRange(year: number): { start: string; end: string } {
  return { start: `${year}-01-01`, end: `${year}-12-31` };
}

const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export function monthShort(month: number): string {
  return MONTHS_SHORT[month - 1] ?? '';
}

export function monthLong(month: number): string {
  return MONTHS_LONG[month - 1] ?? '';
}

/** "2026-11-09" -> "9 Nov" */
export function formatDayShort(iso: string): string {
  const date = parseIsoDate(iso);
  return `${date.getDate()} ${monthShort(date.getMonth() + 1)}`;
}

/** "2026-11-09" -> "Mon 9 Nov 2026" */
export function formatDayLong(iso: string): string {
  const date = parseIsoDate(iso);
  const weekday = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][date.getDay()];
  return `${weekday} ${date.getDate()} ${monthShort(date.getMonth() + 1)} ${date.getFullYear()}`;
}
