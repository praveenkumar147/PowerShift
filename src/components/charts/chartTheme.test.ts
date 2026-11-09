import { describe, expect, it } from 'vitest';
import { niceCeiling } from '@/components/charts/chartTheme';

describe('niceCeiling', () => {
  it('rounds up to a readable axis maximum', () => {
    expect(niceCeiling(3.76)).toBe(4);
    expect(niceCeiling(3.948)).toBe(4);
    expect(niceCeiling(4.3)).toBe(5);
    expect(niceCeiling(0.15)).toBe(0.15);
    expect(niceCeiling(0.16)).toBe(0.2);
    expect(niceCeiling(13)).toBe(15);
    expect(niceCeiling(100)).toBe(100);
    expect(niceCeiling(0)).toBe(1);
  });
});
