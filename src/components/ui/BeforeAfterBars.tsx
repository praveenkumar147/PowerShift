import { cn } from '@/lib/cn';

interface BeforeAfterBarsProps {
  /** Describes the compared quantity for screen readers, e.g. "Monthly bill". */
  label: string;
  before: { label: string; value: number; display: string };
  after: { label: string; value: number; display: string };
  /** Lower is better (bills, peaks). The improved bar is lime; a worse result is amber, never hidden. */
  lowerIsBetter?: boolean;
}

/**
 * Two horizontal bars on a shared scale, so the length difference is the real difference.
 * They grow from the left once when they appear (transform only, no layout work).
 */
export function BeforeAfterBars({ label, before, after, lowerIsBetter = true }: BeforeAfterBarsProps) {
  const max = Math.max(before.value, after.value, Number.EPSILON);
  const improved = lowerIsBetter ? after.value <= before.value : after.value >= before.value;
  const row = (item: BeforeAfterBarsProps['before'], tone: string, delay: number) => (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-muted">{item.label}</span>
        <span className="font-medium tabular-nums">{item.display}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-raised">
        <div
          className={cn('ps-grow-x h-full rounded-full', tone)}
          style={{ width: `${Math.max(2, (item.value / max) * 100)}%`, animationDelay: `${delay}ms` }}
        />
      </div>
    </div>
  );
  return (
    <div role="group" aria-label={label} className="space-y-3">
      {row(before, 'bg-[var(--ps-series-1)]', 0)}
      {row(after, improved ? 'bg-accent' : 'bg-warning', 180)}
    </div>
  );
}
