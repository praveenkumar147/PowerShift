import { useState } from 'react';
import { ApiError, fieldErrorsOf } from '@/api/client';
import { useAppliances } from '@/features/appliances/api';
import { ApplianceFormDialog } from '@/features/appliances/form/ApplianceFormDialog';
import type { Appliance, ApplianceInput } from '@/features/appliances/types';
import { useTariffs } from '@/features/tariffs/api';
import type { ApplianceFormRequest } from '@/features/simulation/editor/ChangeBuilder';
import { ScenarioForm, type Draft } from '@/features/simulation/editor/ScenarioForm';
import { useSaveScenario } from '@/features/simulation/api';
import type { Scenario, SimChange } from '@/features/simulation/types';

const ALL = { search: '', category: '', mode: '' } as const;
const ZERO_ESTIMATES = { max_power_kw: 0, average_power_kw: 0, on_hours_per_day: 0, energy_per_operating_day_kwh: 0, energy_per_week_kwh: 0 };

function toDraft(scenario: Scenario | null): Draft {
  return {
    name: scenario?.name ?? '',
    description: scenario?.description ?? '',
    priority: scenario?.priority ?? 'balanced',
    weight: scenario?.balance_weight ?? 50,
    changes: scenario?.changes ?? [],
  };
}

/** Appliance settings stored in a change, shaped like a real appliance so the form can pre-fill from it. */
function asAppliance(id: number, input: ApplianceInput): Appliance {
  return { ...input, id, estimates: ZERO_ESTIMATES, warnings: [] };
}

type Stage = { kind: 'scenario' } | { kind: 'appliance'; mode: 'add' | 'replace'; replaceId: number | null; index: number | null; prefill: Appliance | null };

interface ScenarioEditorProps {
  scenario: Scenario | null;
  onClose: () => void;
}

/**
 * Owns the scenario being edited. While the appliance form is open the scenario
 * form is not shown (so dialogs never nest), but the draft stays here, so nothing is lost.
 * Nothing in this editor writes to the real household.
 */
export function ScenarioEditor({ scenario, onClose }: ScenarioEditorProps) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(scenario));
  const [stage, setStage] = useState<Stage>({ kind: 'scenario' });
  const save = useSaveScenario(scenario?.id ?? null);
  const appliances = useAppliances(ALL).data ?? [];
  const tariffs = useTariffs().data ?? [];

  const errors = fieldErrorsOf(save.error);
  const generalError = save.error instanceof ApiError && save.error.status !== 422 && !errors.name ? save.error.message : null;
  const update = (changes: Partial<Draft>) => setDraft((current) => ({ ...current, ...changes }));

  function submit() {
    save.mutate(
      {
        name: draft.name,
        description: draft.description.trim() || null,
        priority: draft.priority,
        balance_weight: draft.weight,
        changes: draft.changes,
      },
      { onSuccess: onClose },
    );
  }

  function openApplianceForm(request: ApplianceFormRequest, index: number | null = null) {
    setStage({ kind: 'appliance', mode: request.mode, replaceId: request.replaceId, index, prefill: request.prefill });
  }

  function editChange(index: number) {
    const change = draft.changes[index];
    if (change?.type === 'add_appliance') openApplianceForm({ mode: 'add', replaceId: null, prefill: asAppliance(0, change.appliance) }, index);
    if (change?.type === 'replace_appliance') {
      openApplianceForm({ mode: 'replace', replaceId: change.appliance_id, prefill: asAppliance(change.appliance_id, change.appliance) }, index);
    }
  }

  function applianceSubmitted(input: ApplianceInput) {
    if (stage.kind !== 'appliance') return;
    const change: SimChange =
      stage.mode === 'replace' && stage.replaceId !== null
        ? { type: 'replace_appliance', appliance_id: stage.replaceId, appliance: input }
        : { type: 'add_appliance', appliance: input };
    setDraft((current) => ({
      ...current,
      changes: stage.index === null ? [...current.changes, change] : current.changes.map((c, i) => (i === stage.index ? change : c)),
    }));
    save.reset();
    setStage({ kind: 'scenario' });
  }

  if (stage.kind === 'appliance') {
    const replacing = stage.mode === 'replace';
    return (
      <ApplianceFormDialog
        appliance={stage.prefill}
        onClose={() => setStage({ kind: 'scenario' })}
        onSubmitInput={applianceSubmitted}
        title={replacing ? `Change ${stage.prefill?.name ?? 'appliance'} in this scenario` : 'Add an appliance to this scenario'}
        description="Set the appliance as it should be in this scenario. Your real appliances are not changed."
        submitLabel="Use in scenario"
      />
    );
  }

  return (
    <ScenarioForm
      title={scenario ? `Edit ${scenario.name}` : 'New scenario'}
      draft={draft}
      onChange={(changes) => {
        save.reset();
        update(changes);
      }}
      appliances={appliances}
      tariffs={tariffs}
      errors={errors}
      generalError={generalError}
      saving={save.isPending}
      onSubmit={submit}
      onClose={onClose}
      onOpenApplianceForm={(request) => openApplianceForm(request)}
      onEditChange={editChange}
    />
  );
}
