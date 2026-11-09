import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { ApiError, fieldErrorsOf } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Select, TextInput } from '@/components/ui/inputs';
import { Modal } from '@/components/ui/Modal';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { useHousehold } from '@/features/household/api';
import { useSaveTariff } from '@/features/tariffs/api';
import { ChargesEditor, SlabsEditor, TouPeriodsEditor } from '@/features/tariffs/form/RowEditors';
import { emptyTariffValues, fromTariff, toTariffInput, type FieldErrors, type TariffFormValues } from '@/features/tariffs/formModel';
import { SLAB_MODE_LABELS, TARIFF_TYPE_LABELS, type SlabMode, type Tariff, type TariffType } from '@/features/tariffs/types';

const FORM_ID = 'tariff-form';
const TYPE_OPTIONS = (Object.keys(TARIFF_TYPE_LABELS) as TariffType[]).map((value) => ({ value, label: TARIFF_TYPE_LABELS[value] }));

const TYPE_HELP: Record<TariffType, string> = {
  flat: 'One price per kWh at all times.',
  tou: 'The price depends on the time of day. Shifting appliances to cheaper hours lowers the bill.',
  slab: 'The price depends on how much you use in the month. Shifting appliances in time does not change a slab bill.',
};

/** Error keys shown inside a specific input; anything else is listed at the top. */
function isPlaced(key: string): boolean {
  return (
    ['name', 'effective_date', 'flat_rate_per_kwh', 'tou_periods', 'slabs'].includes(key) ||
    /^(tou_periods|slabs|charges)\.\d+(\.\w+)?$/.test(key)
  );
}

export function TariffFormDialog({ tariff, onClose }: { tariff: Tariff | null; onClose: () => void }) {
  const [values, setValues] = useState<TariffFormValues>(() => (tariff ? fromTariff(tariff) : emptyTariffValues()));
  const [clientErrors, setClientErrors] = useState<FieldErrors>({});
  const save = useSaveTariff(tariff?.id ?? null);
  const currency = useHousehold().data?.currency_code ?? '';
  const rateUnit = currency ? `${currency}/kWh` : 'per kWh';

  const errors: FieldErrors = Object.keys(clientErrors).length ? clientErrors : fieldErrorsOf(save.error);
  const hasErrors = Object.keys(errors).length > 0;
  const unplaced = Object.entries(errors).filter(([key]) => !isPlaced(key));
  const update = (changes: Partial<TariffFormValues>) => setValues((current) => ({ ...current, ...changes }));

  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (!hasErrors) return;
    formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"], p.text-danger')?.scrollIntoView?.({ block: 'center' });
  }, [clientErrors, save.error, hasErrors]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const result = toTariffInput(values);
    if ('errors' in result) {
      setClientErrors(result.errors);
      return;
    }
    setClientErrors({});
    save.mutate(result.input, { onSuccess: onClose });
  }

  return (
    <Modal
      size="lg"
      title={tariff ? `Edit ${tariff.name}` : 'Add tariff'}
      description="Enter the rates from your electricity bill or your utility's published tariff."
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={FORM_ID} disabled={save.isPending}>
            {save.isPending ? 'Saving…' : tariff ? 'Save changes' : 'Add tariff'}
          </Button>
        </>
      }
    >
      <form ref={formRef} id={FORM_ID} onSubmit={onSubmit} noValidate className="space-y-8">
        {(hasErrors || save.isError) && (
          <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
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

        <Section title="Tariff">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name" error={errors.name}>
              {(p) => <TextInput {...p} value={values.name} maxLength={100} onChange={(e) => update({ name: e.target.value })} />}
            </Field>
            <Field label="Effective from" error={errors.effective_date}>
              {(p) => <TextInput {...p} type="date" value={values.effectiveDate} onChange={(e) => update({ effectiveDate: e.target.value })} />}
            </Field>
          </div>
          <div className="space-y-2">
            <SegmentedControl label="Tariff type" options={TYPE_OPTIONS} value={values.tariffType} onChange={(tariffType) => update({ tariffType })} />
            <p className="text-xs text-muted">{TYPE_HELP[values.tariffType]}</p>
          </div>
        </Section>

        <Section title="Energy price">
          {values.tariffType === 'flat' && (
            <div className="md:w-1/2">
              <Field label={`Price (${rateUnit})`} error={errors.flat_rate_per_kwh}>
                {(p) => <TextInput {...p} type="number" min={0} step="any" value={values.flatRate} onChange={(e) => update({ flatRate: e.target.value })} />}
              </Field>
            </div>
          )}
          {values.tariffType === 'tou' && <TouPeriodsEditor values={values} update={update} errors={errors} rateUnit={rateUnit} />}
          {values.tariffType === 'slab' && (
            <>
              <div className="md:w-1/2">
                <Field label="How slabs are charged" hint="Check your utility's rules; most use separate rates per slab.">
                  {(p) => (
                    <Select {...p} value={values.slabMode} onChange={(e) => update({ slabMode: e.target.value as SlabMode })}>
                      {(Object.keys(SLAB_MODE_LABELS) as SlabMode[]).map((m) => (
                        <option key={m} value={m}>
                          {SLAB_MODE_LABELS[m]}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              </div>
              <SlabsEditor values={values} update={update} errors={errors} rateUnit={rateUnit} />
            </>
          )}
        </Section>

        <Section title="Additional charges">
          <ChargesEditor values={values} update={update} errors={errors} currency={currency || 'amount'} />
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
