import { describe, expect, it } from 'vitest';
import {
  formatDuration,
  formatMinute,
  formatWindow,
  parseEndTimeInput,
  parseTimeInput,
  toTimeInput,
} from '@/lib/time';

describe('time helpers', () => {
  it('formats minutes in 24h and 12h styles', () => {
    expect(formatMinute(0)).toBe('00:00');
    expect(formatMinute(1320)).toBe('22:00');
    expect(formatMinute(1440)).toBe('24:00');
    expect(formatMinute(0, '12h')).toBe('12:00 AM');
    expect(formatMinute(750, '12h')).toBe('12:30 PM');
    expect(formatMinute(1320, '12h')).toBe('10:00 PM');
    expect(formatMinute(1440, '12h')).toBe('12:00 AM');
  });

  it('formats windows that wrap midnight', () => {
    expect(formatWindow(1320, 360)).toBe('22:00–06:00');
  });

  it('formats durations', () => {
    expect(formatDuration(90)).toBe('1 h 30 min');
    expect(formatDuration(120)).toBe('2 h');
    expect(formatDuration(45)).toBe('45 min');
  });

  it('round-trips time inputs, treating 00:00 as end-of-day for end times', () => {
    expect(parseTimeInput('07:45')).toBe(465);
    expect(parseTimeInput('00:00')).toBe(0);
    expect(parseEndTimeInput('00:00')).toBe(1440);
    expect(parseEndTimeInput('06:00')).toBe(360);
    expect(toTimeInput(1440)).toBe('00:00');
    expect(toTimeInput(465)).toBe('07:45');
  });

  it('rejects malformed times', () => {
    expect(parseTimeInput('')).toBeNull();
    expect(parseTimeInput('7:45')).toBeNull();
    expect(parseTimeInput('24:00')).toBeNull();
    expect(parseEndTimeInput('')).toBeNull();
  });
});
