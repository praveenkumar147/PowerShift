import type { Tariff } from '@/features/tariffs/types';

type Period = Tariff['tou_periods'][number];

/** The pieces of one period on a 24-hour line (a window that crosses midnight becomes two pieces). */
function pieces(p: Period): Array<{ from: number; to: number }> {
  if (p.end_minute > p.start_minute) return [{ from: p.start_minute, to: p.end_minute }];
  return [
    { from: p.start_minute, to: 1440 },
    { from: 0, to: p.end_minute },
  ].filter((piece) => piece.to > piece.from);
}

/**
 * A 24-hour strip of a time-of-use tariff: darker lime means a higher price. It is a picture of the
 * list next to it (so it is hidden from screen readers), drawn from the tariff's own periods;
 * no rate is assumed. If the tariff has different weekday and weekend prices, the first group is shown.
 */
export function PriceStrip({ periods }: { periods: Period[] }) {
  const dayType = periods[0]?.day_type;
  const shown = periods.filter((p) => p.day_type === dayType);
  if (shown.length === 0) return null;
  const rates = shown.map((p) => p.rate_per_kwh);
  const low = Math.min(...rates);
  const high = Math.max(...rates);

  return (
    <div aria-hidden className="mt-3">
      <div className="relative h-3 overflow-hidden rounded-full bg-surface-raised">
        {shown.flatMap((p, i) =>
          pieces(p).map((piece, j) => (
            <span
              key={`${i}-${j}`}
              className="absolute top-0 h-full bg-accent"
              style={{
                left: `${(piece.from / 1440) * 100}%`,
                width: `${((piece.to - piece.from) / 1440) * 100}%`,
                // Cheapest hours are dim, the most expensive are full lime.
                opacity: high === low ? 0.7 : 0.25 + 0.75 * ((p.rate_per_kwh - low) / (high - low)),
                boxShadow: 'inset -1px 0 0 var(--ps-surface)',
              }}
            />
          )),
        )}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-muted tabular-nums">
        <span>00</span>
        <span>06</span>
        <span>12</span>
        <span>18</span>
        <span>24</span>
      </div>
    </div>
  );
}
