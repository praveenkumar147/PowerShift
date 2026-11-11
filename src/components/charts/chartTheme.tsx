/**
 * Shared chart styling. Colours are CSS variables from index.css, so light/dark
 * themes switch without re-rendering. Marks follow one spec everywhere:
 * thin bars with 4px rounded data ends, recessive grid and axes, and a hover tooltip.
 */
import type { ReactNode } from 'react';

export const SERIES = {
  /** Grey: fixed load, and the "before" side of a comparison. */
  primary: 'var(--ps-series-1)',
  /** Lime (olive in the light theme): flexible load, what the scheduler can move. */
  secondary: 'var(--ps-series-2)',
  /** Single-series charts use the brand lime so the one thing being shown stands out. */
  highlight: 'var(--ps-series-2)',
} as const;

/**
 * Animation settings for every chart: draw in once (and ease between data changes), unless the person
 * asked their system for reduced motion. Recharts does not read that setting itself.
 */
export function chartMotion() {
  const reduce = typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  return { isAnimationActive: !reduce, animationDuration: 650, animationEasing: 'ease-out' } as const;
}

export const AXIS_PROPS = {
  stroke: 'var(--ps-muted)',
  tick: { fill: 'var(--ps-muted)', fontSize: 12 },
  tickLine: false,
  axisLine: false,
} as const;

export const GRID_PROPS = { stroke: 'var(--ps-grid)', vertical: false } as const;

/** Rounded top for vertical bars; for a stack, only the top segment gets it. */
export const BAR_RADIUS_TOP: [number, number, number, number] = [4, 4, 0, 0];
export const BAR_RADIUS_END: [number, number, number, number] = [0, 4, 4, 0];

export const TOOLTIP_CURSOR = { fill: 'var(--ps-accent-soft)', opacity: 0.6 };

/**
 * A tidy axis maximum just above `value`, so ticks land on readable numbers:
 * 3.76 -> 4, 4.3 -> 5, 0.15 -> 0.2, 13 -> 15.
 */
export function niceCeiling(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((m) => m * magnitude >= value) ?? 10;
  return Number((step * magnitude).toPrecision(12));
}

interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

/** Tooltip body in text colours; a small swatch carries the series identity. */
export function TooltipBox({ title, rows }: { title: string; rows: TooltipRow[] }) {
  return (
    <div className="rounded-control border border-border bg-surface-raised px-3 py-2 text-xs shadow-float">
      <p className="mb-1 font-medium text-fg">{title}</p>
      {rows.map((row) => (
        <p key={row.label} className="flex items-center justify-between gap-4 text-muted">
          <span className="flex items-center gap-1.5">
            {row.color && <span aria-hidden className="inline-block size-2 rounded-sm" style={{ background: row.color }} />}
            {row.label}
          </span>
          <span className="font-medium text-fg tabular-nums">{row.value}</span>
        </p>
      ))}
    </div>
  );
}

/** The value axis unit, stated once above the plot instead of on every tick. */
export function AxisUnit({ children }: { children: ReactNode }) {
  return <p className="mb-1 text-xs text-muted">{children}</p>;
}

export function LegendItem({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted">
      <span aria-hidden className="inline-block size-2.5 rounded-sm" style={{ background: color }} />
      {children}
    </span>
  );
}
