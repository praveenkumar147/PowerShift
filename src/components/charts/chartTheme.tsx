/**
 * Shared chart styling. Colours are CSS variables from index.css, so light/dark
 * themes switch without re-rendering. Marks follow one spec everywhere:
 * thin bars with 4px rounded data ends, recessive grid and axes, and a hover tooltip.
 */
import type { ReactNode } from 'react';

export const SERIES = {
  primary: 'var(--ps-series-1)',
  secondary: 'var(--ps-series-2)',
} as const;

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

export const TOOLTIP_CURSOR = { fill: 'var(--ps-grid)', opacity: 0.6 };

interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

/** Tooltip body in text colours; a small swatch carries the series identity. */
export function TooltipBox({ title, rows }: { title: string; rows: TooltipRow[] }) {
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-lg">
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
