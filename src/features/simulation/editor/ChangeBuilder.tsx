import { Plus } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Select, TextInput } from '@/components/ui/inputs';
import type { Appliance } from '@/features/appliances/types';
import type { Tariff } from '@/features/tariffs/types';
import type { SimChange } from '@/features/simulation/types';

type Kind = 'add' | 'copy' | 'replace' | 'remove' | 'tariff' | 'limit';

const KIND_LABELS: Record<Kind, string> = {
  add: 'Add a new appliance',
  copy: 'Add another copy of an appliance',
  replace: 'Change an appliance (power, hours, days, windows…)',
  remove: 'Remove an appliance',
  tariff: 'Use a different tariff',
  limit: 'Change the household load limit',
};

export interface ApplianceFormRequest {
  mode: 'add' | 'replace';
  prefill: Appliance | null;
  replaceId: number | null;
}

interface ChangeBuilderProps {
  appliances: Appliance[];
  tariffs: Tariff[];
  onAddChange: (change: SimChange) => void;
  onOpenApplianceForm: (request: ApplianceFormRequest) => void;
}

const NEEDS_APPLIANCE: ReadonlySet<Kind> = new Set(['copy', 'replace', 'remove']);

/** Lets the user build one change at a time. Nothing here touches real data. */
export function ChangeBuilder({ appliances, tariffs, onAddChange, onOpenApplianceForm }: ChangeBuilderProps) {
  const [kind, setKind] = useState<Kind>('add');
  const [applianceId, setApplianceId] = useState('');
  const [tariffId, setTariffId] = useState('');
  const [limit, setLimit] = useState('');
  const [limitError, setLimitError] = useState<string | null>(null);

  const chosenAppliance = appliances.find((a) => String(a.id) === (applianceId || String(appliances[0]?.id ?? '')));
  const chosenTariff = tariffs.find((t) => String(t.id) === (tariffId || String(tariffs[0]?.id ?? '')));
  const missing =
    (NEEDS_APPLIANCE.has(kind) && !chosenAppliance && 'You have no appliances to choose from.') ||
    (kind === 'tariff' && !chosenTariff && 'You have no saved tariffs. Add one on the Electricity Tariff page.') ||
    null;

  function addChange() {
    setLimitError(null);
    if (kind === 'add') return onOpenApplianceForm({ mode: 'add', prefill: null, replaceId: null });
    if (kind === 'copy' && chosenAppliance) {
      return onOpenApplianceForm({ mode: 'add', prefill: { ...chosenAppliance, name: `${chosenAppliance.name} (copy)` }, replaceId: null });
    }
    if (kind === 'replace' && chosenAppliance) {
      return onOpenApplianceForm({ mode: 'replace', prefill: chosenAppliance, replaceId: chosenAppliance.id });
    }
    if (kind === 'remove' && chosenAppliance) return onAddChange({ type: 'remove_appliance', appliance_id: chosenAppliance.id });
    if (kind === 'tariff' && chosenTariff) return onAddChange({ type: 'change_tariff', tariff_id: chosenTariff.id });
    if (kind === 'limit') {
      const value = Number(limit);
      if (limit.trim() === '' || Number.isNaN(value) || value <= 0) {
        setLimitError('Enter a load limit above 0 kW.');
        return;
      }
      onAddChange({ type: 'set_load_limit', max_load_kw: value });
      setLimit('');
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface-raised p-4">
      <p className="mb-3 text-sm font-medium">Add a change</p>
      <div className="grid items-end gap-3 md:grid-cols-[1fr_1fr_auto]">
        <Field label="What to change">
          {(p) => (
            <Select {...p} value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
              {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABELS[k]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div>
          {NEEDS_APPLIANCE.has(kind) && (
            <Field label="Appliance">
              {(p) => (
                <Select {...p} value={chosenAppliance ? String(chosenAppliance.id) : ''} onChange={(e) => setApplianceId(e.target.value)}>
                  {appliances.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          {kind === 'tariff' && (
            <Field label="Tariff">
              {(p) => (
                <Select {...p} value={chosenTariff ? String(chosenTariff.id) : ''} onChange={(e) => setTariffId(e.target.value)}>
                  {tariffs.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                      {t.is_active ? ' (active)' : ''}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          {kind === 'limit' && (
            <Field label="New load limit (kW)" error={limitError ?? undefined}>
              {(p) => <TextInput {...p} type="number" min={0.1} step={0.1} value={limit} onChange={(e) => setLimit(e.target.value)} />}
            </Field>
          )}
        </div>
        <Button variant="secondary" onClick={addChange} disabled={Boolean(missing)}>
          <Plus aria-hidden className="size-4" /> {kind === 'add' || kind === 'copy' || kind === 'replace' ? 'Continue' : 'Add change'}
        </Button>
      </div>
      {missing && <p className="mt-2 text-xs text-muted">{missing}</p>}
    </div>
  );
}
