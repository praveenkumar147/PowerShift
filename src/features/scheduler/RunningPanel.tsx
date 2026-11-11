import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { ProgressBeam } from '@/components/ui/ProgressBeam';
import { PRIORITY_LABELS, type OptimizationRequest } from '@/features/scheduler/types';

/** Whole seconds since the panel appeared (it only exists while the solver runs). Read from the clock, not guessed. */
function useElapsedSeconds(): number {
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, []);
  return Math.max(0, Math.floor((now - startedAt) / 1000));
}

/**
 * Shown while the solver runs. It reports only what is true: the goal, the real elapsed time and the
 * time limit the person chose. It never shows a percentage, because the solver cannot tell us how far
 * along it is, and an invented number would be a lie.
 */
export function RunningPanel({ request }: { request: OptimizationRequest | undefined }) {
  const elapsed = useElapsedSeconds();
  return (
    <Card title="Optimizing" description="The solver is searching for the best start times, then every result is re-checked independently.">
      <div role="status" aria-label="Optimizing" className="space-y-4">
        <ProgressBeam label="Optimization in progress" />
        <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
          {request && (
            <div>
              <dt className="text-xs uppercase tracking-wider text-muted">Goal</dt>
              <dd className="mt-0.5 font-medium">{PRIORITY_LABELS[request.priority]}</dd>
            </div>
          )}
          <div>
            <dt className="text-xs uppercase tracking-wider text-muted">Elapsed</dt>
            <dd className="mt-0.5 font-medium tabular-nums">{elapsed} s</dd>
          </div>
          {request && (
            <div>
              <dt className="text-xs uppercase tracking-wider text-muted">Stops at the latest after</dt>
              <dd className="mt-0.5 font-medium tabular-nums">{request.time_limit_seconds} s</dd>
            </div>
          )}
        </dl>
      </div>
    </Card>
  );
}
