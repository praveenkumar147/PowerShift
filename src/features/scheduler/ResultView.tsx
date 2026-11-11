import { AlertTriangle, ArrowRight, CheckCircle2, XCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { ChartCard } from '@/components/charts/ChartCard';
import { Card } from '@/components/ui/Card';
import { NotesBox } from '@/components/ui/NotesBox';
import { StatTile } from '@/components/ui/StatTile';
import { WEEKDAY_SHORT } from '@/features/appliances/types';
import { LoadProfileChart } from '@/features/peak-load/charts/LoadProfileChart';
import { PRIORITY_LABELS, STAGE_LABELS, type OptimizationRun, type ScheduleItem, type ValidationCheck } from '@/features/scheduler/types';
import { cn } from '@/lib/cn';
import { formatDateTime, monthLong } from '@/lib/dates';
import { formatKw, formatMoney } from '@/lib/format';
import { formatDuration, formatMinute, formatWindow, type TimeFormat } from '@/lib/time';

interface ResultViewProps {
  run: OptimizationRun;
  currency: string | null;
  timeFormat: TimeFormat;
}

type Tone = 'success' | 'warning' | 'danger';

const TONE_CLASSES: Record<Tone, string> = {
  success: 'border-success/30 bg-success/5 text-success',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  danger: 'border-danger/30 bg-danger/5 text-danger',
};

/** What the run's status means, in words that never overstate it. */
function verdict(run: OptimizationRun): { tone: Tone; title: string; detail: string } {
  const found = run.status === 'OPTIMAL' || run.status === 'FEASIBLE';
  if (found && !run.schedule_valid) {
    return {
      tone: 'danger',
      title: 'The schedule failed independent validation',
      detail: 'The solver returned a schedule, but a re-check found a problem. It is not shown as a recommendation.',
    };
  }
  switch (run.status) {
    case 'OPTIMAL':
      return { tone: 'success', title: 'Optimal schedule found and verified', detail: 'Proven best for the chosen goal, and every independent check passed.' };
    case 'FEASIBLE':
      return {
        tone: 'warning',
        title: 'Valid schedule found, not proven optimal',
        detail: 'Every independent check passed, but the time limit ran out before the solver could prove nothing better exists.',
      };
    case 'INFEASIBLE':
      return { tone: 'danger', title: 'No valid schedule exists', detail: 'The constraints cannot all be satisfied at once.' };
    case 'UNKNOWN':
      return { tone: 'warning', title: 'No schedule found within the time limit', detail: 'Try a longer time limit or coarser start times.' };
    case 'MODEL_INVALID':
      return { tone: 'danger', title: 'Internal model error', detail: 'The optimization model was rejected by the solver. This is a bug in PowerShift.' };
  }
}

function Banner({ tone, title, children }: { tone: Tone; title: string; children: ReactNode }) {
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'warning' ? AlertTriangle : XCircle;
  return (
    <div role="status" className={cn('rounded-xl border px-4 py-3 text-sm', TONE_CLASSES[tone])}>
      <p className="flex items-center gap-2 font-medium">
        <Icon aria-hidden className="size-4" /> {title}
      </p>
      <div className="mt-1 pl-6 text-fg">{children}</div>
    </div>
  );
}

export function ResultView({ run, currency, timeFormat }: ResultViewProps) {
  const v = verdict(run);
  const month = monthLong(run.bill_month);

  return (
    <div className="space-y-6">
      <p className="text-xs text-muted">
        Run #{run.id} · {formatDateTime(run.created_at)} · goal: {PRIORITY_LABELS[run.priority]}
        {run.priority === 'balanced' && ` (cost ${run.balance_weight}%, peak ${100 - run.balance_weight}%)`}. Results reflect your settings at
        the time of the run.
      </p>

      <Banner tone={v.tone} title={v.title}>
        <p>{v.detail}</p>
        {run.diagnostics.length > 0 && (
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {run.diagnostics.map((d) => (
              <li key={d.code + d.message}>{d.message}</li>
            ))}
          </ul>
        )}
      </Banner>

      {run.schedule_valid && run.optimized && (
        <>
          <Tiles run={run} currency={currency} month={month} />
          <ScheduleTable items={run.items} timeFormat={timeFormat} />
          {run.profile && (
            <ChartCard
              title={`Load profile on ${WEEKDAY_SHORT[run.profile.weekday]}, before and after`}
              description="The day with the highest peak in your current schedule. Worst-case demand in 15-minute steps, same scale."
            >
              <div className="grid gap-6 lg:grid-cols-2">
                {(['before', 'after'] as const).map((which) => (
                  <div key={which}>
                    <h3 className="mb-2 text-sm font-medium">{which === 'before' ? 'Current schedule' : 'Optimized schedule'}</h3>
                    <LoadProfileChart
                      compact
                      steps={run.profile?.[which] ?? []}
                      appliances={run.appliances}
                      limitKw={run.load_limit_kw}
                      timeFormat={timeFormat}
                      scaleToKw={run.baseline.peak_kw}
                    />
                  </div>
                ))}
              </div>
            </ChartCard>
          )}
        </>
      )}

      {run.validation.length > 0 && <ValidationCard checks={run.validation} />}
      <SolverDetails run={run} />
      <NotesBox notes={run.notes} title="About these results" />
    </div>
  );
}

function Tiles({ run, currency, month }: { run: OptimizationRun; currency: string | null; month: string }) {
  const before = run.baseline;
  const after = run.optimized;
  if (!after) return null;
  const savings = run.monthly_savings;
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <StatTile
        label={`Estimated bill, ${month}`}
        value={after.monthly_bill !== null ? formatMoney(after.monthly_bill, currency) : 'No tariff'}
        detail={before.monthly_bill !== null ? `Current schedule: ${formatMoney(before.monthly_bill, currency)}` : 'Add a tariff to see costs'}
      />
      <StatTile
        label="Estimated savings"
        value={savings === null ? '—' : formatMoney(savings, currency)}
        detail={savings === null ? undefined : savings < 0 ? 'Costs more than your current schedule' : 'Per month, estimated'}
      />
      <StatTile label="Peak demand (worst case)" value={formatKw(after.peak_kw)} detail={`Current schedule: ${formatKw(before.peak_kw)}`} />
      <StatTile
        label="Time over load limit"
        value={run.load_limit_kw === null ? '—' : `${after.minutes_over_limit} min/week`}
        detail={run.load_limit_kw === null ? 'No limit set' : `Current schedule: ${before.minutes_over_limit} min/week`}
      />
    </div>
  );
}

/** Recommended start/end times with reasons. Shared with the Simulation Lab. */
export function ScheduleTable({ items, timeFormat }: { items: ScheduleItem[]; timeFormat: TimeFormat }) {
  return (
    <Card title="Recommended schedule" description="One start time per flexible appliance, used on every day it runs.">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Recommended start and end times with reasons</caption>
          <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">Appliance</th>
              <th scope="col" className="py-2 pr-4 font-medium">Usual start</th>
              <th scope="col" className="py-2 pr-4 font-medium">Recommended</th>
              <th scope="col" className="py-2 font-medium">Why</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border align-top">
            {items.map((item) => (
              <tr key={item.appliance_id}>
                <th scope="row" className="py-3 pr-4 font-medium">
                  {item.name}
                  <span className="block text-xs font-normal text-muted">
                    {formatKw(item.power_kw)} · {formatDuration(item.duration_minutes)}
                  </span>
                </th>
                <td className="py-3 pr-4 whitespace-nowrap tabular-nums">{formatMinute(item.baseline_start_minute, timeFormat)}</td>
                <td className="py-3 pr-4 whitespace-nowrap tabular-nums">
                  {item.moved ? (
                    <span className="flex items-center gap-1.5 font-medium text-accent">
                      <ArrowRight aria-hidden className="size-3.5" />
                      {formatWindow(item.start_minute, item.end_minute, timeFormat)}
                    </span>
                  ) : (
                    <span className="text-muted">No change ({formatWindow(item.start_minute, item.end_minute, timeFormat)})</span>
                  )}
                </td>
                <td className="py-3">
                  <ul className="space-y-1">
                    {item.reasons.map((reason) => (
                      <li key={reason.code}>{reason.text}</li>
                    ))}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** The independent checks of a schedule. Shared with the Simulation Lab. */
export function ValidationCard({ checks }: { checks: ValidationCheck[] }) {
  const passed = checks.filter((c) => c.passed).length;
  return (
    <Card
      title="Independent validation"
      description={`${passed} of ${checks.length} checks passed. Re-checked from your appliance settings, without using the solver.`}
    >
      <ul className="space-y-2 text-sm">
        {checks.map((check) => (
          <li key={check.code} className="flex items-start gap-2">
            {check.passed ? (
              <CheckCircle2 aria-label="Passed" className="mt-0.5 size-4 shrink-0 text-success" />
            ) : (
              <XCircle aria-label="Failed" className="mt-0.5 size-4 shrink-0 text-danger" />
            )}
            <span>
              {check.label}
              <span className="block text-xs text-muted">{check.detail}</span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function SolverDetails({ run }: { run: OptimizationRun }) {
  return (
    <details className="rounded-xl border border-border bg-surface p-4 text-sm shadow-sm">
      <summary className="cursor-pointer font-medium">
        Solver details: {run.status}, {run.solve_time_ms} ms
      </summary>
      <div className="mt-3 grid gap-x-6 gap-y-1 text-muted sm:grid-cols-2">
        <div>Solver: {run.solver}</div>
        <div>Random seed: {run.random_seed} (single worker, reproducible)</div>
        <div>Start-time step: {run.start_step_minutes} min</div>
        <div>Time limit: {run.time_limit_seconds} s</div>
      </div>
      <table className="mt-3 w-full text-left tabular-nums">
        <caption className="sr-only">Optimization stages</caption>
        <thead className="text-xs uppercase tracking-wide text-muted">
          <tr>
            <th scope="col" className="py-1 pr-4 font-medium">Stage</th>
            <th scope="col" className="py-1 pr-4 font-medium">Status</th>
            <th scope="col" className="py-1 text-right font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {run.stages.map((stage, i) => (
            <tr key={stage.name}>
              <td className="py-1 pr-4">
                {i + 1}. {STAGE_LABELS[stage.name] ?? stage.name}
              </td>
              <td className="py-1 pr-4">{stage.status}</td>
              <td className="py-1 text-right">{Math.round(stage.seconds * 1000)} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
