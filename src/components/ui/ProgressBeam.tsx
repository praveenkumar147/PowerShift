import { cn } from '@/lib/cn';

/**
 * An indeterminate progress bar: a lime beam sweeping across a track.
 *
 * It deliberately shows NO percentage. The solver cannot say how far along it is, and inventing a
 * number would be a lie. Pair it with real facts instead (elapsed time, what is being worked on).
 */
export function ProgressBeam({ label, className }: { label: string; className?: string }) {
  return (
    <div role="progressbar" aria-label={label} aria-busy="true" className={cn('h-1.5 w-full overflow-hidden rounded-full bg-surface-raised', className)}>
      <div className="h-full w-2/5 animate-beam rounded-full bg-accent" />
    </div>
  );
}
