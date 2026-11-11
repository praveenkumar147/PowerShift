import { ChevronDown, ChevronUp, Pencil, Play, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PRIORITY_LABELS } from '@/features/scheduler/types';
import { ResultDetails } from '@/features/simulation/results/ResultDetails';
import type { Scenario } from '@/features/simulation/types';
import { formatDateTime } from '@/lib/dates';
import { formatSignedKw, formatSignedKwh, formatSignedMoney } from '@/lib/format';
import type { TimeFormat } from '@/lib/time';

interface ScenarioCardProps {
  scenario: Scenario;
  currency: string | null;
  timeFormat: TimeFormat;
  running: boolean;
  expanded: boolean;
  onRun: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onToggle: () => void;
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string | undefined }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 text-lg font-semibold tabular-nums">{value}</dd>
      {hint && <dd className="text-xs text-muted">{hint}</dd>}
    </div>
  );
}

export function ScenarioCard({ scenario, currency, timeFormat, running, expanded, onRun, onEdit, onDelete, onToggle }: ScenarioCardProps) {
  const result = scenario.latest_result;
  const priority = PRIORITY_LABELS[scenario.priority];

  return (
    <article aria-label={scenario.name} className="rounded-xl border border-border bg-surface p-6 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold">{scenario.name}</h2>
            <Badge>{priority} goal</Badge>
            {scenario.result_is_stale && <Badge tone="warning">Edited since last run</Badge>}
          </div>
          {scenario.description && <p className="mt-0.5 text-sm text-muted">{scenario.description}</p>}
        </div>
        <div className="flex gap-1">
          <Button onClick={onRun} disabled={running}>
            <Play aria-hidden className="size-4" /> {running ? 'Running…' : result ? 'Run again' : 'Run scenario'}
          </Button>
          <Button variant="ghost" aria-label={`Edit ${scenario.name}`} onClick={onEdit}>
            <Pencil aria-hidden className="size-4" />
          </Button>
          <Button variant="ghost" aria-label={`Delete ${scenario.name}`} onClick={onDelete}>
            <Trash2 aria-hidden className="size-4" />
          </Button>
        </div>
      </header>

      <div className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">What changes</h3>
        {scenario.change_descriptions.length === 0 ? (
          <p className="mt-1 text-sm text-muted">Nothing: compares the {priority.toLowerCase()} scheduling goal on your current household.</p>
        ) : (
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
            {scenario.change_descriptions.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        )}
      </div>

      {result ? (
        <>
          <dl className="mt-5 grid gap-4 border-t border-border pt-4 md:grid-cols-4">
            <Stat label="Energy" value={`${formatSignedKwh(result.kwh_change)}`} hint="per month, vs current" />
            <Stat
              label="Bill, usual times"
              value={result.bill_change === null ? '—' : formatSignedMoney(result.bill_change, currency)}
              hint={result.bill_change === null ? 'No tariff' : 'per month, vs current'}
            />
            <Stat
              label="Bill, after scheduling"
              value={result.optimized_bill_change === null ? '—' : formatSignedMoney(result.optimized_bill_change, currency)}
              hint={result.optimized_bill_change === null ? 'No valid schedule' : 'per month, vs current'}
            />
            <Stat label="Peak demand" value={formatSignedKw(result.peak_change_kw)} hint={result.optimized ? 'after scheduling, vs current' : 'usual times, vs current'} />
          </dl>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted">Run {formatDateTime(result.created_at)}. Estimates; your real household was not changed.</p>
            <Button variant="ghost" onClick={onToggle} aria-expanded={expanded}>
              {expanded ? <ChevronUp aria-hidden className="size-4" /> : <ChevronDown aria-hidden className="size-4" />}
              {expanded ? 'Hide details' : 'Show details'}
            </Button>
          </div>
          {expanded && <ResultDetails result={result} timeFormat={timeFormat} />}
        </>
      ) : (
        <p className="mt-5 border-t border-border pt-4 text-sm text-muted">Not run yet.</p>
      )}
    </article>
  );
}
