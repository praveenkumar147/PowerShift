import { CalendarClock } from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Spinner } from '@/components/ui/Spinner';
import { useHousehold, useTimeFormat } from '@/features/household/api';
import { useOptimizationHistory, useOptimizationRun, useRunOptimization } from '@/features/scheduler/api';
import { ResultView } from '@/features/scheduler/ResultView';
import { RunControls } from '@/features/scheduler/RunControls';
import { PRIORITY_LABELS, type OptimizationSummary } from '@/features/scheduler/types';
import { formatDateTime } from '@/lib/dates';
import { formatKw, formatMoney } from '@/lib/format';

export function SchedulerPage() {
  const history = useOptimizationHistory();
  const optimize = useRunOptimization();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  // Until the user picks or runs something, show the most recent run.
  const shownId = selectedId ?? history.data?.[0]?.id ?? null;
  const run = useOptimizationRun(shownId);
  const currency = useHousehold().data?.currency_code ?? null;
  const timeFormat = useTimeFormat();

  return (
    <>
      <PageHeader
        title="Smart Scheduler"
        description="Finds the best start times for your flexible appliances with a mathematical solver (Google OR-Tools CP-SAT)."
      />
      <div className="space-y-6">
        <RunControls
          running={optimize.isPending}
          error={optimize.isError ? optimize.error.message : null}
          onRun={(request) => optimize.mutate(request, { onSuccess: (result) => setSelectedId(result.id) })}
        />

        {optimize.isPending && <Spinner label="Optimizing" />}
        {run.isError && (
          <p role="alert" className="text-sm text-danger">
            {run.error.message}
          </p>
        )}
        {!optimize.isPending && run.data && <ResultView run={run.data} currency={currency} timeFormat={timeFormat} />}

        {history.isSuccess && history.data.length === 0 && !optimize.isPending && (
          <EmptyState
            icon={CalendarClock}
            title="No optimization runs yet"
            message="Choose a goal above and select Optimize schedule. Your household settings are never changed by a run."
          />
        )}
        {history.data && history.data.length > 0 && (
          <HistoryTable runs={history.data} shownId={shownId} currency={currency} onSelect={setSelectedId} />
        )}
      </div>
    </>
  );
}

interface HistoryTableProps {
  runs: OptimizationSummary[];
  shownId: number | null;
  currency: string | null;
  onSelect: (id: number) => void;
}

function HistoryTable({ runs, shownId, currency, onSelect }: HistoryTableProps) {
  const change = (before: string, after: string | null) => (after === null ? before : `${before} → ${after}`);
  return (
    <Card title="History" description="Previous runs, most recent first.">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm tabular-nums">
          <caption className="sr-only">Optimization history</caption>
          <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">Run</th>
              <th scope="col" className="py-2 pr-4 font-medium">Goal</th>
              <th scope="col" className="py-2 pr-4 font-medium">Result</th>
              <th scope="col" className="py-2 pr-4 font-medium">Monthly bill</th>
              <th scope="col" className="py-2 pr-4 font-medium">Peak</th>
              <th scope="col" className="py-2"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {runs.map((r) => (
              <tr key={r.id} className={r.id === shownId ? 'bg-accent-soft/40' : undefined}>
                <td className="py-2 pr-4 whitespace-nowrap">
                  #{r.id} <span className="text-muted">· {formatDateTime(r.created_at)}</span>
                </td>
                <td className="py-2 pr-4">{PRIORITY_LABELS[r.priority]}</td>
                <td className="py-2 pr-4">
                  <Badge tone={r.schedule_valid ? (r.status === 'OPTIMAL' ? 'accent' : 'warning') : 'neutral'}>
                    {r.schedule_valid ? r.status : r.status === 'OPTIMAL' || r.status === 'FEASIBLE' ? 'INVALID' : r.status}
                  </Badge>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {r.baseline_bill === null
                    ? '—'
                    : change(formatMoney(r.baseline_bill, currency), r.optimized_bill === null ? null : formatMoney(r.optimized_bill, currency))}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {change(formatKw(r.baseline_peak_kw), r.optimized_peak_kw === null ? null : formatKw(r.optimized_peak_kw))}
                </td>
                <td className="py-2 text-right">
                  {r.id === shownId ? (
                    <span className="text-xs text-muted">Shown above</span>
                  ) : (
                    <button type="button" onClick={() => onSelect(r.id)} className="rounded px-2 py-1 text-accent hover:bg-accent-soft">
                      View<span className="sr-only"> run #{r.id}</span>
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
