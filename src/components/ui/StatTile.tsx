import { revealDelay } from '@/components/ui/Card';
import { cn } from '@/lib/cn';

interface StatTileProps {
  label: string;
  value: string;
  detail?: string | undefined;
  /** Lime value: the one number on the screen that matters most (savings, an optimum). */
  highlight?: boolean;
  index?: number;
  floating?: boolean;
}

/** A single headline number. Used where a chart would add nothing. */
export function StatTile({ label, value, detail, highlight = false, index = 0, floating = false }: StatTileProps) {
  return (
    <div
      style={revealDelay(index)}
      className={cn(
        'animate-rise rounded-card border bg-surface p-5 shadow-card',
        highlight ? 'border-accent-ink/40' : 'border-border',
        floating && 'motion-safe:animate-float',
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wider text-muted">{label}</p>
      <p className={cn('mt-2 truncate font-display text-[1.7rem] font-semibold leading-none tabular-nums', highlight && 'text-accent-ink')} title={value}>
        {value}
      </p>
      {detail && (
        <p className="mt-2 truncate text-xs text-muted" title={detail}>
          {detail}
        </p>
      )}
    </div>
  );
}
