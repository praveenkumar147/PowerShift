import { describe, expect, it } from 'vitest';
import { formatDayLong, formatDayShort, monthRange, parseIsoDate, toIsoDate, yearRange } from '@/lib/dates';

describe('date helpers', () => {
  it('parses ISO dates as local dates and back', () => {
    expect(toIsoDate(parseIsoDate('2026-11-09'))).toBe('2026-11-09');
    expect(parseIsoDate('2026-11-09').getDate()).toBe(9);
  });

  it('computes month and year ranges, including leap years', () => {
    expect(monthRange(2026, 11)).toEqual({ start: '2026-11-01', end: '2026-11-30' });
    expect(monthRange(2024, 2)).toEqual({ start: '2024-02-01', end: '2024-02-29' });
    expect(monthRange(2026, 12)).toEqual({ start: '2026-12-01', end: '2026-12-31' });
    expect(yearRange(2026)).toEqual({ start: '2026-01-01', end: '2026-12-31' });
  });

  it('formats days', () => {
    expect(formatDayShort('2026-11-09')).toBe('9 Nov');
    expect(formatDayLong('2026-11-09')).toBe('Mon 9 Nov 2026');
  });
});
