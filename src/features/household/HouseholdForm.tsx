import { CheckCircle2 } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { fieldErrorsOf } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Select, TextInput } from '@/components/ui/inputs';
import { useSaveHousehold, type Household } from '@/features/household/api';
import type { TimeFormat } from '@/lib/time';

interface FormValues {
  name: string;
  occupants: string;
  locationLabel: string;
  maxLoadKw: string;
  currencyCode: string;
  timeFormat: TimeFormat;
}

function toFormValues(household: Household | null): FormValues {
  return {
    name: household?.name ?? '',
    occupants: household ? String(household.occupants) : '',
    locationLabel: household?.location_label ?? '',
    maxLoadKw: household ? String(household.max_load_kw) : '',
    currencyCode: household?.currency_code ?? '',
    timeFormat: household?.time_format ?? '24h',
  };
}

/** Converts form strings to the API shape; returns field errors for unparseable values. */
function toHousehold(values: FormValues): { household: Household } | { errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const occupants = Number(values.occupants);
  const maxLoad = Number(values.maxLoadKw);
  if (!values.name.trim()) errors.name = 'Enter a name for the household.';
  if (!values.occupants || !Number.isInteger(occupants)) errors.occupants = 'Enter a whole number.';
  if (!values.maxLoadKw || Number.isNaN(maxLoad)) errors.max_load_kw = 'Enter a number in kW.';
  if (!values.currencyCode.trim()) errors.currency_code = 'Enter a 3-letter currency code.';
  if (Object.keys(errors).length) return { errors };

  return {
    household: {
      name: values.name,
      occupants,
      location_label: values.locationLabel || null,
      max_load_kw: maxLoad,
      currency_code: values.currencyCode,
      time_format: values.timeFormat,
    },
  };
}

export function HouseholdForm({ household }: { household: Household | null }) {
  const [values, setValues] = useState(() => toFormValues(household));
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const save = useSaveHousehold();
  const errors = { ...fieldErrorsOf(save.error), ...clientErrors };

  const set = (key: keyof FormValues) => (value: string) => {
    save.reset();
    setValues((current) => ({ ...current, [key]: value }));
  };

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const result = toHousehold(values);
    if ('errors' in result) {
      setClientErrors(result.errors);
      return;
    }
    setClientErrors({});
    save.mutate(result.household);
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <div className="grid gap-5 md:grid-cols-2">
        <Field label="Household name" error={errors.name}>
          {(p) => <TextInput {...p} value={values.name} onChange={(e) => set('name')(e.target.value)} maxLength={100} />}
        </Field>
        <Field label="Location (optional)" hint="For your reference only. Tariffs are never assumed from it." error={errors.location_label}>
          {(p) => (
            <TextInput {...p} value={values.locationLabel} onChange={(e) => set('locationLabel')(e.target.value)} maxLength={100} />
          )}
        </Field>
        <Field label="Number of occupants" error={errors.occupants}>
          {(p) => (
            <TextInput {...p} type="number" min={1} max={50} step={1} value={values.occupants} onChange={(e) => set('occupants')(e.target.value)} />
          )}
        </Field>
        <Field
          label="Maximum household load (kW)"
          hint="The most power your connection allows at one moment, e.g. your sanctioned load."
          error={errors.max_load_kw}
        >
          {(p) => (
            <TextInput {...p} type="number" min={0.1} step={0.1} value={values.maxLoadKw} onChange={(e) => set('maxLoadKw')(e.target.value)} />
          )}
        </Field>
        <Field label="Currency code" hint="3 letters, e.g. INR, USD, EUR. Used for display only." error={errors.currency_code}>
          {(p) => (
            <TextInput {...p} value={values.currencyCode} onChange={(e) => set('currencyCode')(e.target.value.toUpperCase())} maxLength={3} className="uppercase" />
          )}
        </Field>
        <Field label="Time format" error={errors.time_format}>
          {(p) => (
            <Select {...p} value={values.timeFormat} onChange={(e) => set('timeFormat')(e.target.value)}>
              <option value="24h">24-hour (22:00)</option>
              <option value="12h">12-hour (10:00 PM)</option>
            </Select>
          )}
        </Field>
      </div>

      {save.isError && Object.keys(fieldErrorsOf(save.error)).length === 0 && (
        <p role="alert" className="text-sm text-danger">
          {save.error.message}
        </p>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : household ? 'Save changes' : 'Save household'}
        </Button>
        {save.isSuccess && (
          <span role="status" className="flex items-center gap-1.5 text-sm text-success">
            <CheckCircle2 aria-hidden className="size-4" /> Saved
          </span>
        )}
      </div>
    </form>
  );
}
