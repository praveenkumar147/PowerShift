import { CalendarClock, Clock } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { ApiError, fieldErrorsOf } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Checkbox, Select, TextInput } from '@/components/ui/inputs';
import { Modal } from '@/components/ui/Modal';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { useSaveAppliance } from '@/features/appliances/api';
import { FixedBlocksEditor, FlexibleFields, WeekdayPicker } from '@/features/appliances/form/UsageFields';
import {
  emptyFormValues,
  fromAppliance,
  toApplianceInput,
  type ApplianceFormValues,
  type FieldErrors,
} from '@/features/appliances/formModel';
import { CATEGORIES, CATEGORY_LABELS, PRIORITY_LABELS, type Appliance, type ApplianceInput, type ApplianceMode, type Priority } from '@/features/appliances/types';

const FORM_ID = 'appliance-form';

const MODE_OPTIONS = [
  { value: 'fixed', label: 'Fixed schedule', icon: Clock },
  { value: 'flexible', label: 'Flexible', icon: CalendarClock },
] as const satisfies ReadonlyArray<{ value: ApplianceMode; label: string; icon: typeof Clock }>;

const MODE_HELP: Record<ApplianceMode, string> = {
  fixed: 'Runs at set times and is not moved by the scheduler (fridge, router, lights).',
  flexible: 'Its start time can move within a window you allow (washing machine, dishwasher, water heater).',
};

/** Error keys shown next to a specific input; anything else is listed at the top. */
function isPlacedField(key: string): boolean {
  return (
    ['name', 'category', 'rated_power_w', 'quantity', 'duty_cycle', 'priority', 'operating_days', 'fixed_blocks', 'flexible'].includes(key) ||
    key.startsWith('flexible.') ||
    /^fixed_blocks\.\d+\.(start|end)_minute$/.test(key)
  );
}

interface ApplianceFormDialogProps {
  appliance: Appliance | null;
  onClose: () => void;
  /**
   * When given, the form hands the validated values to the caller instead of saving
   * the appliance (the Simulation Lab uses this: nothing is written to the household).
   */
  onSubmitInput?: (input: ApplianceInput) => void;
  title?: string;
  description?: string;
  submitLabel?: string;
}

export function ApplianceFormDialog({ appliance, onClose, onSubmitInput, title, description, submitLabel }: ApplianceFormDialogProps) {
  const [values, setValues] = useState<ApplianceFormValues>(() => (appliance ? fromAppliance(appliance) : emptyFormValues()));
  const [clientErrors, setClientErrors] = useState<FieldErrors>({});
  const save = useSaveAppliance(appliance?.id ?? null);

  const errors: FieldErrors = Object.keys(clientErrors).length ? clientErrors : fieldErrorsOf(save.error);
  const unplaced = Object.entries(errors).filter(([key]) => !isPlacedField(key));
  const hasErrors = Object.keys(errors).length > 0;

  const update = (changes: Partial<ApplianceFormValues>) => setValues((current) => ({ ...current, ...changes }));

  // When new errors appear, bring the first problem into view: the form is long
  // and the message may be below the visible part of the dialog.
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (!hasErrors) return;
    const firstProblem = formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"], p.text-danger');
    firstProblem?.scrollIntoView?.({ block: 'center' });
  }, [clientErrors, save.error, hasErrors]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const result = toApplianceInput(values);
    if ('errors' in result) {
      setClientErrors(result.errors);
      return;
    }
    setClientErrors({});
    if (onSubmitInput) {
      onSubmitInput(result.input);
      return;
    }
    save.mutate(result.input, { onSuccess: onClose });
  }

  return (
    <Modal
      size="lg"
      title={title ?? (appliance ? `Edit ${appliance.name}` : 'Add appliance')}
      description={description ?? 'Values are your estimates; PowerShift does not measure consumption.'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={FORM_ID} disabled={save.isPending}>
            {save.isPending ? 'Saving…' : (submitLabel ?? (appliance ? 'Save changes' : 'Add appliance'))}
          </Button>
        </>
      }
    >
      <form ref={formRef} id={FORM_ID} onSubmit={onSubmit} noValidate className="space-y-8">
        {hasErrors && (
          <div role="alert" className="rounded-control border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
            <p className="font-medium">
              {save.error instanceof ApiError && save.error.status !== 422 ? save.error.message : 'Some values need attention.'}
            </p>
            {unplaced.length > 0 && (
              <ul className="mt-1 list-disc pl-5">
                {unplaced.map(([key, message]) => (
                  <li key={key}>{message}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {save.isError && !hasErrors && (
          <p role="alert" className="text-sm text-danger">
            {save.error.message}
          </p>
        )}

        <Section title="Appliance">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name" error={errors.name}>
              {(p) => <TextInput {...p} value={values.name} maxLength={100} onChange={(e) => update({ name: e.target.value })} />}
            </Field>
            <Field label="Category" error={errors.category}>
              {(p) => (
                <Select {...p} value={values.category} onChange={(e) => update({ category: e.target.value as ApplianceFormValues['category'] })}>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {CATEGORY_LABELS[c]}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Rated power (W)" hint="From the label: power of one unit at full load." error={errors.rated_power_w}>
              {(p) => <TextInput {...p} type="number" min={1} step="any" value={values.ratedPowerW} onChange={(e) => update({ ratedPowerW: e.target.value })} />}
            </Field>
            <Field label="Quantity" error={errors.quantity}>
              {(p) => <TextInput {...p} type="number" min={1} max={100} step={1} value={values.quantity} onChange={(e) => update({ quantity: e.target.value })} />}
            </Field>
            <Field
              label="Duty cycle (%)"
              hint="Share of on-time it actually draws rated power. Fridge ≈ 40%, kettle or heater 100%."
              error={errors.duty_cycle}
            >
              {(p) => (
                <TextInput {...p} type="number" min={1} max={100} step="any" value={values.dutyCyclePercent} onChange={(e) => update({ dutyCyclePercent: e.target.value })} />
              )}
            </Field>
          </div>
        </Section>

        <Section title="Usage">
          <div className="space-y-2">
            <SegmentedControl label="Usage type" options={MODE_OPTIONS} value={values.mode} onChange={(mode) => update({ mode })} />
            <p className="text-xs text-muted">{MODE_HELP[values.mode]}</p>
          </div>
          <WeekdayPicker values={values} update={update} errors={errors} />
          {values.mode === 'fixed' ? (
            <FixedBlocksEditor values={values} update={update} errors={errors} />
          ) : (
            <FlexibleFields values={values} update={update} errors={errors} />
          )}
        </Section>

        <Section title="Scheduling">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Priority" hint="Used by the scheduler when not everything fits." error={errors.priority}>
              {(p) => (
                <Select {...p} value={values.priority} onChange={(e) => update({ priority: e.target.value as Priority })}>
                  {(Object.keys(PRIORITY_LABELS) as Priority[]).map((priority) => (
                    <option key={priority} value={priority}>
                      {PRIORITY_LABELS[priority]}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Checkbox
            label="Can run at the same time as other heavy appliances"
            description="Untick to keep it from overlapping with other appliances that are also unticked."
            checked={values.allowSimultaneous}
            onChange={(e) => update({ allowSimultaneous: e.target.checked })}
          />
        </Section>
      </form>
    </Modal>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-4">
      <legend className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">{title}</legend>
      {children}
    </fieldset>
  );
}
