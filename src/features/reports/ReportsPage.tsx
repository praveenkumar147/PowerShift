import { CheckCircle2, Download } from 'lucide-react';
import { useState } from 'react';
import { ApiError, fieldErrorsOf } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { LinkButton } from '@/components/ui/LinkButton';
import { PageHeader } from '@/components/ui/PageHeader';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { useExportReport, type ReportParams } from '@/features/reports/api';
import { EVERY_REPORT_STATES, FORMAT_HELP, REPORTS, type ReportDefinition, type ReportFormat } from '@/features/reports/catalog';
import { ReportOptions, type OptionValues } from '@/features/reports/ReportOptions';
import { useOptimizationHistory } from '@/features/scheduler/api';
import { useScenarios } from '@/features/simulation/api';
import { monthRange } from '@/lib/dates';
import { cn } from '@/lib/cn';

const FORMATS = [
  { value: 'csv', label: 'CSV (spreadsheet)' },
  { value: 'pdf', label: 'PDF (document)' },
] as const satisfies ReadonlyArray<{ value: ReportFormat; label: string }>;

function initialOptions(): OptionValues {
  const now = new Date();
  return {
    ...monthRange(now.getFullYear(), now.getMonth() + 1),
    category: '',
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    weekday: '',
    runId: '',
    scenarioIds: [],
  };
}

/** Only the options a report actually uses are sent. */
function toParams(report: ReportDefinition, v: OptionValues, allScenarioIds: number[]): ReportParams {
  const p: ReportParams = {};
  const uses = (param: ReportDefinition['params'][number]) => report.params.includes(param);
  if (uses('range')) Object.assign(p, { start: v.start, end: v.end });
  if (uses('category') && v.category) p.category = v.category;
  if (uses('year') || uses('monthOfYear')) p.year = v.year;
  if (uses('monthOfYear')) p.month = v.month;
  if (uses('weekday') && v.weekday !== '') p.weekday = Number(v.weekday);
  if (uses('run') && v.runId !== '') p.run_id = Number(v.runId);
  if (uses('scenarios')) {
    const everything = allScenarioIds.every((id) => v.scenarioIds.includes(id));
    if (!everything || v.scenarioIds.length === 0) p.scenario_ids = v.scenarioIds;
  }
  return p;
}

export function ReportsPage() {
  const [kind, setKind] = useState(REPORTS[0]?.kind ?? 'daily_energy');
  const [format, setFormat] = useState<ReportFormat>('pdf');
  const [options, setOptions] = useState<OptionValues>(initialOptions);
  // Scenarios the user unticked. Storing exclusions (not selections) means new scenarios start ticked.
  const [excluded, setExcluded] = useState<number[]>([]);
  const exportReport = useExportReport();
  const history = useOptimizationHistory();
  const scenarioList = useScenarios();
  const runs = history.data ?? [];
  const scenarios = (scenarioList.data ?? []).filter((s) => s.latest_result !== null);
  const scenarioIds = scenarios.map((s) => s.id);

  const selectedScenarioIds = scenarioIds.filter((id) => !excluded.includes(id));
  const values: OptionValues = { ...options, scenarioIds: selectedScenarioIds };

  const report = REPORTS.find((r) => r.kind === kind) ?? REPORTS[0];
  if (!report) return null;

  // Never say "none yet" when the truth is "could not look": a failed or slow request is its own state.
  const source = report.kind === 'optimization_comparison' ? history : report.kind === 'simulation_comparison' ? scenarioList : null;
  const unavailable = source?.isError
    ? { text: `Could not load the data this report needs: ${source.error.message}`, to: null, label: '' }
    : source?.isPending
      ? { text: 'Loading the data this report needs…', to: null, label: '' }
      : null;
  const missingData =
    unavailable ||
    (report.kind === 'optimization_comparison' && runs.length === 0 && { text: 'No optimization runs yet. Run the Smart Scheduler first.', to: '/scheduler', label: 'Open Smart Scheduler' }) ||
    (report.kind === 'simulation_comparison' && scenarios.length === 0 && { text: 'No scenario has been run yet. Run a scenario in the Simulation Lab first.', to: '/simulation', label: 'Open Simulation Lab' }) ||
    null;
  const noScenarioChosen = report.kind === 'simulation_comparison' && selectedScenarioIds.length === 0;

  const errors = fieldErrorsOf(exportReport.error);
  const generalError = exportReport.error && Object.keys(errors).length === 0 ? exportReport.error.message : null;
  const update = (changes: Partial<OptionValues>) => {
    exportReport.reset();
    const { scenarioIds: ticked, ...rest } = changes;
    if (ticked) setExcluded(scenarioIds.filter((id) => !ticked.includes(id)));
    setOptions((current) => ({ ...current, ...rest }));
  };

  return (
    <>
      <PageHeader title="Reports" description="Export estimates as a spreadsheet or a PDF. Everything is generated on your computer." />
      <div className="grid gap-6 lg:grid-cols-5">
        <section aria-label="Choose a report" className="lg:col-span-2">
          <div role="radiogroup" aria-label="Report" className="space-y-2">
            {REPORTS.map((r) => (
              <button
                key={r.kind}
                type="button"
                role="radio"
                aria-checked={r.kind === kind}
                onClick={() => {
                  exportReport.reset();
                  setKind(r.kind);
                }}
                className={cn(
                  'w-full rounded-xl border p-4 text-left transition-colors',
                  r.kind === kind ? 'border-accent bg-accent-soft' : 'border-border bg-surface hover:bg-surface-raised',
                )}
              >
                <span className="block text-sm font-semibold">{r.title}</span>
                <span className="mt-0.5 block text-xs text-muted">{r.description}</span>
              </button>
            ))}
          </div>
        </section>

        <div className="space-y-6 lg:col-span-3">
          <Card title={report.title} description={report.description}>
            <ul className="mb-5 list-disc space-y-0.5 pl-5 text-sm text-muted">
              {report.includes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>

            <ReportOptions params={report.params} values={values} onChange={update} runs={runs} scenarios={scenarios} errors={errors} />

            <div className="mt-6 space-y-2">
              <SegmentedControl label="File format" options={FORMATS} value={format} onChange={(f) => setFormat(f)} />
              <p className="text-xs text-muted">{FORMAT_HELP[format]}</p>
            </div>

            {missingData && (
              <div role="status" className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface-raised px-4 py-3 text-sm">
                <span className="text-muted">{missingData.text}</span>
                {missingData.to && <LinkButton to={missingData.to}>{missingData.label}</LinkButton>}
              </div>
            )}
            {generalError && (
              <p role="alert" className="mt-4 rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
                {exportReport.error instanceof ApiError && exportReport.error.status === 0 ? 'The PowerShift backend is not responding.' : generalError}
              </p>
            )}

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button
                disabled={exportReport.isPending || Boolean(missingData) || noScenarioChosen}
                onClick={() => exportReport.mutate({ type: report.kind, format, params: toParams(report, values, scenarioIds) })}
              >
                <Download aria-hidden className="size-4" /> {exportReport.isPending ? 'Preparing…' : `Export ${format.toUpperCase()}`}
              </Button>
              {exportReport.isSuccess && (
                <span role="status" className="flex items-center gap-1.5 text-sm text-success">
                  <CheckCircle2 aria-hidden className="size-4" /> Download started: {exportReport.data}
                </span>
              )}
            </div>
          </Card>

          <section aria-label="What every report states" className="rounded-xl border border-border bg-surface-raised p-4 text-sm text-muted">
            <p className="mb-2 font-medium text-fg">Every report states</p>
            <ul className="list-disc space-y-1 pl-5">
              {EVERY_REPORT_STATES.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
