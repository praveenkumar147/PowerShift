import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AXIS_PROPS, BAR_RADIUS_END, TOOLTIP_CURSOR, TooltipBox } from '@/components/charts/chartTheme';
import { Card } from '@/components/ui/Card';
import { PRIORITY_LABELS } from '@/features/scheduler/types';
import type { Scenario, SimMetrics, SimulationResult } from '@/features/simulation/types';
import { formatKw, formatKwh, formatMoney, formatSignedKw, formatSignedKwh, formatSignedMoney } from '@/lib/format';

interface ComparisonCardProps {
  scenarios: Scenario[];
  currency: string | null;
}

interface Column {
  scenario: Scenario;
  result: SimulationResult;
}

const CURRENT_COLOR = 'var(--ps-muted)';
const SCENARIO_COLOR = 'var(--ps-series-1)';

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
}

interface BarDatum {
  label: string;
  bill: number;
  current: boolean;
}

/** Baselines can differ if the real household changed between runs; then the comparison is not fair. */
function baselinesDiffer(columns: Column[]): boolean {
  const [first, ...rest] = columns.map((c) => c.result.baseline);
  if (!first) return false;
  const same = (a: SimMetrics, b: SimMetrics) => a.monthly_kwh === b.monthly_kwh && a.monthly_bill === b.monthly_bill && a.peak_kw === b.peak_kw;
  return rest.some((b) => !same(first, b));
}

function Delta({ children }: { children: string }) {
  return <span className="block text-xs text-muted">{children}</span>;
}

/** Side-by-side comparison of every scenario that has a result, against the current household. */
export function ComparisonCard({ scenarios, currency }: ComparisonCardProps) {
  const columns: Column[] = scenarios.flatMap((scenario) => (scenario.latest_result ? [{ scenario, result: scenario.latest_result }] : []));
  const first = columns[0];
  if (!first) return null;
  const base = first.result.baseline;
  const month = new Date(first.result.bill_year, first.result.bill_month - 1).toLocaleString('en', { month: 'long' });
  const money = (value: number | null) => (value === null ? '—' : formatMoney(value, currency));
  const billAfter = (r: SimulationResult) => r.optimized?.monthly_bill ?? r.scenario.monthly_bill;

  const chartData: BarDatum[] = [
    ...(base.monthly_bill === null ? [] : [{ label: 'Current household', bill: base.monthly_bill, current: true }]),
    ...columns.flatMap(({ result }) => {
      const bill = billAfter(result);
      return bill === null ? [] : [{ label: result.scenario_name, bill, current: false }];
    }),
  ];

  const renderTooltip = ({ active, payload }: TooltipProps) => {
    const datum = payload?.[0]?.payload as BarDatum | undefined;
    if (!active || !datum) return null;
    return <TooltipBox title={datum.label} rows={[{ label: 'Estimated bill', value: formatMoney(datum.bill, currency), color: datum.current ? CURRENT_COLOR : SCENARIO_COLOR }]} />;
  };

  return (
    <Card title="Comparison" description={`Estimated figures for ${month}, each scenario against your current household.`}>
      {baselinesDiffer(columns) && (
        <p role="status" className="mb-4 flex items-start gap-2 rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          Some results were calculated when your household was different, so the comparison is not fair. Run all scenarios again.
        </p>
      )}

      {chartData.length > 1 && (
        <div className="mb-6">
          <p className="mb-1 text-xs text-muted">
            Estimated monthly bill ({currency ?? 'currency'}), after scheduling where available
          </p>
          <div style={{ height: chartData.length * 36 + 8 }} role="img" aria-label="Bar chart of the estimated monthly bill for the current household and each scenario">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 96, bottom: 0, left: 0 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="label" {...AXIS_PROPS} width={150} />
                <Tooltip cursor={TOOLTIP_CURSOR} content={renderTooltip} />
                <Bar
                  dataKey="bill"
                  radius={BAR_RADIUS_END}
                  maxBarSize={18}
                  isAnimationActive={false}
                  label={{ position: 'right', fill: 'var(--ps-muted)', fontSize: 12, formatter: (v: unknown) => formatMoney(Number(v), currency) }}
                >
                  {chartData.map((d) => (
                    <Cell key={d.label} fill={d.current ? CURRENT_COLOR : SCENARIO_COLOR} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm tabular-nums">
          <caption className="sr-only">Scenario comparison</caption>
          <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">Per month</th>
              <th scope="col" className="py-2 pr-4 font-medium">Current household</th>
              {columns.map(({ scenario }) => (
                <th key={scenario.id} scope="col" className="py-2 pr-4 font-medium normal-case tracking-normal text-fg">
                  {scenario.name}
                  <span className="block text-xs font-normal text-muted">{PRIORITY_LABELS[scenario.priority]} goal</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border align-top">
            <Row label="Estimated energy" current={formatKwh(base.monthly_kwh)}>
              {columns.map(({ result }) => (
                <Cell2 key={result.id} value={formatKwh(result.scenario.monthly_kwh)} delta={formatSignedKwh(result.kwh_change)} />
              ))}
            </Row>
            <Row label="Estimated bill, usual times" current={money(base.monthly_bill)}>
              {columns.map(({ result }) => (
                <Cell2 key={result.id} value={money(result.scenario.monthly_bill)} delta={result.bill_change === null ? undefined : formatSignedMoney(result.bill_change, currency)} />
              ))}
            </Row>
            <Row label="Estimated bill, after scheduling" current="—">
              {columns.map(({ result }) => (
                <Cell2
                  key={result.id}
                  value={money(result.optimized?.monthly_bill ?? null)}
                  delta={result.optimized_bill_change === null ? undefined : formatSignedMoney(result.optimized_bill_change, currency)}
                />
              ))}
            </Row>
            <Row label="Saved by scheduling" current="—">
              {columns.map(({ result }) => (
                <Cell2 key={result.id} value={result.optimization_savings === null ? '—' : formatMoney(result.optimization_savings, currency)} />
              ))}
            </Row>
            <Row label="Peak demand (worst case), usual times" current={formatKw(base.peak_kw)}>
              {columns.map(({ result }) => (
                <Cell2 key={result.id} value={formatKw(result.scenario.peak_kw)} delta={formatSignedKw(result.scenario.peak_kw - base.peak_kw)} />
              ))}
            </Row>
            <Row label="Peak demand, after scheduling" current="—">
              {columns.map(({ result }) => (
                <Cell2 key={result.id} value={result.optimized ? formatKw(result.optimized.peak_kw) : '—'} delta={result.optimized ? formatSignedKw(result.optimized.peak_kw - base.peak_kw) : undefined} />
              ))}
            </Row>
            <Row label="Over the load limit, usual times" current={`${base.minutes_over_limit} min/week`}>
              {columns.map(({ result }) => (
                <Cell2 key={result.id} value={`${result.scenario.minutes_over_limit} min/week`} />
              ))}
            </Row>
            <Row label="Scheduling result" current="—">
              {columns.map(({ result }) => (
                <Cell2 key={result.id} value={result.status ? (result.schedule_valid ? (result.proven_optimal ? 'Optimal' : 'Valid, not proven optimal') : result.status === 'INFEASIBLE' ? 'No valid schedule' : 'Not available') : 'Not attempted'} />
              ))}
            </Row>
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted">
        Differences (+ costs more, − saves) are relative to your current household. Estimates, not measurements.
      </p>
    </Card>
  );
}

function Row({ label, current, children }: { label: string; current: string; children: ReactNode }) {
  return (
    <tr>
      <th scope="row" className="py-2 pr-4 font-normal text-muted">{label}</th>
      <td className="py-2 pr-4">{current}</td>
      {children}
    </tr>
  );
}

function Cell2({ value, delta }: { value: string; delta?: string | undefined }) {
  return (
    <td className="py-2 pr-4">
      {value}
      {delta && <Delta>{delta}</Delta>}
    </td>
  );
}
