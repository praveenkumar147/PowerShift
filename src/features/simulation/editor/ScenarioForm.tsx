import { Pencil, Trash2 } from 'lucide-react';
import type { FormEvent } from 'react';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { TextInput } from '@/components/ui/inputs';
import { Modal } from '@/components/ui/Modal';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import type { Appliance } from '@/features/appliances/types';
import { PRIORITY_LABELS, type Priority } from '@/features/scheduler/types';
import type { Tariff } from '@/features/tariffs/types';
import { ChangeBuilder, type ApplianceFormRequest } from '@/features/simulation/editor/ChangeBuilder';
import type { SimChange } from '@/features/simulation/types';

export interface Draft {
  name: string;
  description: string;
  priority: Priority;
  weight: number;
  changes: SimChange[];
}

const GOALS = (['cost', 'balanced', 'peak'] as const).map((value) => ({ value, label: PRIORITY_LABELS[value] }));
export const FORM_ID = 'scenario-form';

/** Short text for a change in the draft list (the server returns fuller descriptions after saving). */
export function describeDraftChange(change: SimChange, appliances: Appliance[], tariffs: Tariff[]): string {
  const nameOf = (id: number) => appliances.find((a) => a.id === id)?.name ?? `appliance #${id}`;
  switch (change.type) {
    case 'add_appliance':
      return `Add "${change.appliance.name}"`;
    case 'replace_appliance': {
      const old = nameOf(change.appliance_id);
      return `Change "${old}"${change.appliance.name !== old ? ` (renamed "${change.appliance.name}")` : ''}`;
    }
    case 'remove_appliance':
      return `Remove "${nameOf(change.appliance_id)}"`;
    case 'change_tariff':
      return `Use tariff "${tariffs.find((t) => t.id === change.tariff_id)?.name ?? `#${change.tariff_id}`}"`;
    case 'set_load_limit':
      return `Set load limit to ${change.max_load_kw} kW`;
  }
}

interface ScenarioFormProps {
  title: string;
  draft: Draft;
  onChange: (changes: Partial<Draft>) => void;
  appliances: Appliance[];
  tariffs: Tariff[];
  errors: Record<string, string>;
  generalError: string | null;
  saving: boolean;
  onSubmit: () => void;
  onClose: () => void;
  onOpenApplianceForm: (request: ApplianceFormRequest) => void;
  onEditChange: (index: number) => void;
}

function messagesFor(errors: Record<string, string>, index: number): string[] {
  const prefix = `changes.${index}`;
  return Object.entries(errors)
    .filter(([key]) => key === prefix || key.startsWith(`${prefix}.`))
    .map(([, message]) => message);
}

export function ScenarioForm(props: ScenarioFormProps) {
  const { draft, onChange, appliances, tariffs, errors, generalError } = props;
  const general = [generalError, errors.changes].filter((m): m is string => Boolean(m));

  function submit(event: FormEvent) {
    event.preventDefault();
    props.onSubmit();
  }

  return (
    <Modal
      size="lg"
      title={props.title}
      description="A scenario is a set of what-if changes. It is calculated on a copy: your real appliances, tariffs and household are never changed."
      onClose={props.onClose}
      footer={
        <>
          <Button variant="secondary" onClick={props.onClose}>
            Cancel
          </Button>
          <Button type="submit" form={FORM_ID} disabled={props.saving}>
            {props.saving ? 'Saving…' : 'Save scenario'}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-6">
        {general.length > 0 && (
          <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
            {general.map((m) => (
              <p key={m}>{m}</p>
            ))}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Name" error={errors.name}>
            {(p) => <TextInput {...p} value={draft.name} maxLength={100} placeholder="e.g. Add a bedroom AC" onChange={(e) => onChange({ name: e.target.value })} />}
          </Field>
          <Field label="Description (optional)">
            {(p) => <TextInput {...p} value={draft.description} maxLength={500} onChange={(e) => onChange({ description: e.target.value })} />}
          </Field>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">Scheduling goal for this scenario</p>
          <SegmentedControl label="Scheduling goal" options={GOALS} value={draft.priority} onChange={(priority) => onChange({ priority })} />
          {draft.priority === 'balanced' && (
            <div>
              <label htmlFor="scenario-weight" className="sr-only">
                Balance between cost and peak
              </label>
              <input
                id="scenario-weight"
                type="range"
                min={0}
                max={100}
                step={5}
                value={draft.weight}
                onChange={(e) => onChange({ weight: Number(e.target.value) })}
                aria-valuetext={`Cost ${draft.weight}%, peak ${100 - draft.weight}%`}
                className="w-full accent-[var(--ps-accent)]"
              />
              <p className="text-xs text-muted tabular-nums">
                Cost {draft.weight}% · Peak {100 - draft.weight}%
              </p>
            </div>
          )}
        </div>

        <section aria-label="Changes" className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Changes</h3>
          {draft.changes.length === 0 ? (
            <p className="text-sm text-muted">
              No changes yet. With none, the scenario compares scheduling goals on your current household.
            </p>
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {draft.changes.map((change, index) => (
                <li key={index} className="flex items-start justify-between gap-3 px-4 py-3 text-sm">
                  <div>
                    <p>{describeDraftChange(change, appliances, tariffs)}</p>
                    {messagesFor(errors, index).map((message) => (
                      <p key={message} className="mt-1 text-xs text-danger">
                        {message}
                      </p>
                    ))}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    {(change.type === 'add_appliance' || change.type === 'replace_appliance') && (
                      <Button variant="ghost" aria-label={`Edit change ${index + 1}`} onClick={() => props.onEditChange(index)}>
                        <Pencil aria-hidden className="size-4" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      aria-label={`Remove change ${index + 1}`}
                      onClick={() => onChange({ changes: draft.changes.filter((_, i) => i !== index) })}
                    >
                      <Trash2 aria-hidden className="size-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <ChangeBuilder
            appliances={appliances}
            tariffs={tariffs}
            onAddChange={(change) => onChange({ changes: [...draft.changes, change] })}
            onOpenApplianceForm={props.onOpenApplianceForm}
          />
        </section>
      </form>
    </Modal>
  );
}
