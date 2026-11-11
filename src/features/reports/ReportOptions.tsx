import { Field } from '@/components/ui/Field';
import { Checkbox, Select, TextInput } from '@/components/ui/inputs';
import { CATEGORIES, CATEGORY_LABELS, WEEKDAY_SHORT } from '@/features/appliances/types';
import type { ParamKind } from '@/features/reports/catalog';
import type { OptimizationSummary } from '@/features/scheduler/types';
import type { Scenario } from '@/features/simulation/types';
import { formatDateTime, monthLong } from '@/lib/dates';
import { PRIORITY_LABELS } from '@/features/scheduler/types';

export interface OptionValues {
  start: string;
  end: string;
  category: string;
  year: number;
  month: number;
  /** '' = the day with the highest peak */
  weekday: string;
  /** '' = the latest run */
  runId: string;
  /** Ids of scenarios to include. */
  scenarioIds: number[];
}

interface ReportOptionsProps {
  params: ParamKind[];
  values: OptionValues;
  onChange: (changes: Partial<OptionValues>) => void;
  runs: OptimizationSummary[];
  /** Scenarios that have a result (only those can be reported). */
  scenarios: Scenario[];
  errors: Record<string, string>;
}

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

export function ReportOptions({ params, values, onChange, runs, scenarios, errors }: ReportOptionsProps) {
  const has = (param: ParamKind) => params.includes(param);
  return (
    <div className="space-y-4">
      {has('range') && (
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="From" error={errors.start}>
            {(p) => <TextInput {...p} type="date" value={values.start} max={values.end} onChange={(e) => e.target.value && onChange({ start: e.target.value })} />}
          </Field>
          <Field label="To" error={errors.end} hint="Up to 366 days.">
            {(p) => <TextInput {...p} type="date" value={values.end} min={values.start} onChange={(e) => e.target.value && onChange({ end: e.target.value })} />}
          </Field>
        </div>
      )}

      {has('year') && (
        <div className="md:w-1/2">
          <Field label="Year" error={errors.year}>
            {(p) => <TextInput {...p} type="number" min={2000} max={2100} value={values.year} onChange={(e) => onChange({ year: Number(e.target.value) })} />}
          </Field>
        </div>
      )}

      {has('monthOfYear') && (
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Month" error={errors.month}>
            {(p) => (
              <Select {...p} value={values.month} onChange={(e) => onChange({ month: Number(e.target.value) })}>
                {MONTHS.map((m) => (
                  <option key={m} value={m}>
                    {monthLong(m)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Year" error={errors.year}>
            {(p) => <TextInput {...p} type="number" min={2000} max={2100} value={values.year} onChange={(e) => onChange({ year: Number(e.target.value) })} />}
          </Field>
        </div>
      )}

      {has('category') && (
        <div className="md:w-1/2">
          <Field label="Category">
            {(p) => (
              <Select {...p} value={values.category} onChange={(e) => onChange({ category: e.target.value })}>
                <option value="">All categories</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_LABELS[c]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      )}

      {has('weekday') && (
        <div className="md:w-1/2">
          <Field label="Day" error={errors.weekday}>
            {(p) => (
              <Select {...p} value={values.weekday} onChange={(e) => onChange({ weekday: e.target.value })}>
                <option value="">The day with the highest peak</option>
                {WEEKDAY_SHORT.map((label, i) => (
                  <option key={label} value={i}>
                    {label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      )}

      {has('run') && (
        <div className="md:w-2/3">
          <Field label="Optimization run" error={errors.run_id}>
            {(p) => (
              <Select {...p} value={values.runId} disabled={runs.length === 0} onChange={(e) => onChange({ runId: e.target.value })}>
                <option value="">Latest run</option>
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    #{r.id} · {formatDateTime(r.created_at)} · {PRIORITY_LABELS[r.priority]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      )}

      {has('scenarios') && (
        <fieldset className="space-y-2" aria-describedby="scenarios-help">
          <legend className="text-sm font-medium">Scenarios to include</legend>
          <p id="scenarios-help" className="text-xs text-muted">
            Only scenarios that have been run can be reported.
          </p>
          {errors.scenario_ids && <p className="text-xs text-danger">{errors.scenario_ids}</p>}
          {scenarios.map((s) => (
            <Checkbox
              key={s.id}
              label={s.name}
              checked={values.scenarioIds.includes(s.id)}
              onChange={(e) =>
                onChange({ scenarioIds: e.target.checked ? [...values.scenarioIds, s.id] : values.scenarioIds.filter((id) => id !== s.id) })
              }
            />
          ))}
        </fieldset>
      )}
    </div>
  );
}
