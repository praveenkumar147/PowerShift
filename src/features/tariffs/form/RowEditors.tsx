import { Plus, Trash2 } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Select, TextInput } from '@/components/ui/inputs';
import type { ChargeValues, FieldErrors, PeriodValues, SlabValues, TariffFormValues } from '@/features/tariffs/formModel';
import { CHARGE_KIND_LABELS, DAY_TYPE_LABELS, type ChargeKind, type DayType } from '@/features/tariffs/types';

type Update = (changes: Partial<TariffFormValues>) => void;

interface EditorProps {
  values: TariffFormValues;
  update: Update;
  errors: FieldErrors;
  rateUnit: string;
}

const TIME_STEP_SECONDS = 15 * 60;

function replaceAt<T>(items: T[], index: number, changes: Partial<T>): T[] {
  return items.map((item, i) => (i === index ? { ...item, ...changes } : item));
}

function RowShell({ children, onRemove, removeLabel, canRemove }: { children: ReactNode; onRemove: () => void; removeLabel: string; canRemove: boolean }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-surface-raised p-3">
      <div className="grid flex-1 gap-3 md:grid-cols-4">{children}</div>
      <Button variant="ghost" className="mt-6" aria-label={removeLabel} disabled={!canRemove} onClick={onRemove}>
        <Trash2 aria-hidden className="size-4" />
      </Button>
    </div>
  );
}

function SectionError({ message }: { message: string | undefined }) {
  return message ? <p className="text-sm text-danger">{message}</p> : null;
}

export function TouPeriodsEditor({ values, update, errors, rateUnit }: EditorProps) {
  const set = (index: number, changes: Partial<PeriodValues>) => update({ periods: replaceAt(values.periods, index, changes) });
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Periods must cover all 24 hours exactly once, either every day or separately for weekdays and weekends. An end
        time earlier than the start runs past midnight; 00:00 as an end means midnight.
      </p>
      <SectionError message={errors.tou_periods} />
      {values.periods.map((period, i) => (
        <RowShell key={i} removeLabel={`Remove period ${i + 1}`} canRemove={values.periods.length > 1} onRemove={() => update({ periods: values.periods.filter((_, j) => j !== i) })}>
          <Field label={`Period ${i + 1} days`}>
            {(p) => (
              <Select {...p} value={period.dayType} onChange={(e) => set(i, { dayType: e.target.value as DayType })}>
                {(Object.keys(DAY_TYPE_LABELS) as DayType[]).map((d) => (
                  <option key={d} value={d}>
                    {DAY_TYPE_LABELS[d]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="From" error={errors[`tou_periods.${i}.start_minute`]}>
            {(p) => <TextInput {...p} type="time" step={TIME_STEP_SECONDS} value={period.start} onChange={(e) => set(i, { start: e.target.value })} />}
          </Field>
          <Field label="Until" error={errors[`tou_periods.${i}.end_minute`]}>
            {(p) => <TextInput {...p} type="time" step={TIME_STEP_SECONDS} value={period.end} onChange={(e) => set(i, { end: e.target.value })} />}
          </Field>
          <Field label={`Rate (${rateUnit})`} error={errors[`tou_periods.${i}.rate_per_kwh`]}>
            {(p) => <TextInput {...p} type="number" min={0} step="any" value={period.rate} onChange={(e) => set(i, { rate: e.target.value })} />}
          </Field>
        </RowShell>
      ))}
      <Button variant="secondary" onClick={() => update({ periods: [...values.periods, { dayType: values.periods.at(-1)?.dayType ?? 'all', start: '', end: '', rate: '' }] })}>
        <Plus aria-hidden className="size-4" /> Add period
      </Button>
    </div>
  );
}

export function SlabsEditor({ values, update, errors, rateUnit }: EditorProps) {
  const set = (index: number, changes: Partial<SlabValues>) => update({ slabs: replaceAt(values.slabs, index, changes) });
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Slabs are bands of monthly consumption. Leave the last slab's upper limit empty; it covers everything above.
      </p>
      <SectionError message={errors.slabs} />
      {values.slabs.map((slab, i) => {
        const from = i === 0 ? '0' : values.slabs[i - 1]?.upTo || '…';
        return (
          <RowShell key={i} removeLabel={`Remove slab ${i + 1}`} canRemove={values.slabs.length > 1} onRemove={() => update({ slabs: values.slabs.filter((_, j) => j !== i) })}>
            <div className="text-sm md:col-span-2">
              <span className="block text-sm font-medium">Slab {i + 1}</span>
              <span className="mt-2 block text-muted">
                From {from} kWh {slab.upTo ? `up to ${slab.upTo} kWh` : 'and above'}
              </span>
            </div>
            <Field label="Up to (kWh)" error={errors[`slabs.${i}.up_to_kwh`]}>
              {(p) => <TextInput {...p} type="number" min={0} step="any" placeholder="No limit" value={slab.upTo} onChange={(e) => set(i, { upTo: e.target.value })} />}
            </Field>
            <Field label={`Rate (${rateUnit})`} error={errors[`slabs.${i}.rate_per_kwh`]}>
              {(p) => <TextInput {...p} type="number" min={0} step="any" value={slab.rate} onChange={(e) => set(i, { rate: e.target.value })} />}
            </Field>
          </RowShell>
        );
      })}
      <Button variant="secondary" onClick={() => update({ slabs: [...values.slabs, { upTo: '', rate: '' }] })}>
        <Plus aria-hidden className="size-4" /> Add slab
      </Button>
    </div>
  );
}

const AMOUNT_UNIT: Record<ChargeKind, (currency: string) => string> = {
  fixed_monthly: (c) => `${c} per month`,
  per_kwh: (c) => `${c} per kWh`,
  percentage: () => '% of subtotal',
};

export function ChargesEditor({ values, update, errors, currency }: Omit<EditorProps, 'rateUnit'> & { currency: string }) {
  const set = (index: number, changes: Partial<ChargeValues>) => update({ charges: replaceAt(values.charges, index, changes) });
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Added after the energy charge. Percentages apply to the subtotal of energy, fixed and per-kWh charges.
      </p>
      {values.charges.length === 0 && <p className="text-sm text-muted">No additional charges.</p>}
      {values.charges.map((charge, i) => (
        <RowShell key={i} removeLabel={`Remove charge ${i + 1}`} canRemove onRemove={() => update({ charges: values.charges.filter((_, j) => j !== i) })}>
          <Field label={`Charge ${i + 1} type`}>
            {(p) => (
              <Select {...p} value={charge.kind} onChange={(e) => set(i, { kind: e.target.value as ChargeKind })}>
                {(Object.keys(CHARGE_KIND_LABELS) as ChargeKind[]).map((k) => (
                  <option key={k} value={k}>
                    {CHARGE_KIND_LABELS[k]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="md:col-span-2">
            <Field label="Label" error={errors[`charges.${i}.label`]}>
              {(p) => <TextInput {...p} value={charge.label} maxLength={100} placeholder="e.g. Meter rent" onChange={(e) => set(i, { label: e.target.value })} />}
            </Field>
          </div>
          <Field label={`Amount (${AMOUNT_UNIT[charge.kind](currency)})`} error={errors[`charges.${i}.amount`] ?? errors[`charges.${i}`]}>
            {(p) => <TextInput {...p} type="number" min={0} step="any" value={charge.amount} onChange={(e) => set(i, { amount: e.target.value })} />}
          </Field>
        </RowShell>
      ))}
      <Button variant="secondary" onClick={() => update({ charges: [...values.charges, { kind: 'fixed_monthly', label: '', amount: '' }] })}>
        <Plus aria-hidden className="size-4" /> Add charge
      </Button>
    </div>
  );
}
