import { FlaskConical, Plus } from 'lucide-react';
import { useState } from 'react';
import { fieldErrorsOf } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Spinner } from '@/components/ui/Spinner';
import { useHousehold, useTimeFormat } from '@/features/household/api';
import { useDeleteScenario, useRunScenario, useScenarios } from '@/features/simulation/api';
import { ScenarioEditor } from '@/features/simulation/editor/ScenarioEditor';
import { ComparisonCard } from '@/features/simulation/results/ComparisonCard';
import { ScenarioCard } from '@/features/simulation/results/ScenarioCard';
import type { Scenario } from '@/features/simulation/types';

type Dialog = { kind: 'closed' } | { kind: 'edit'; scenario: Scenario | null } | { kind: 'delete'; scenario: Scenario };

export function SimulationPage() {
  const scenarios = useScenarios();
  const run = useRunScenario();
  const deletion = useDeleteScenario();
  const currency = useHousehold().data?.currency_code ?? null;
  const timeFormat = useTimeFormat();
  const [dialog, setDialog] = useState<Dialog>({ kind: 'closed' });
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [runningId, setRunningId] = useState<number | null>(null);

  const close = () => {
    deletion.reset();
    setDialog({ kind: 'closed' });
  };
  const openNew = () => setDialog({ kind: 'edit', scenario: null });

  function runScenario(id: number) {
    setRunningId(id);
    run.mutate(id, {
      onSuccess: () => setExpandedId(id),
      onSettled: () => setRunningId(null),
    });
  }

  return (
    <>
      <PageHeader
        title="Simulation Lab"
        description="Try what-if scenarios on a copy of your household. Your real appliances, tariffs and settings are never changed."
        actions={
          <Button onClick={openNew}>
            <Plus aria-hidden className="size-4" /> New scenario
          </Button>
        }
      />

      {scenarios.isPending && <Spinner label="Loading scenarios" />}
      {scenarios.isError && (
        <p role="alert" className="text-sm text-danger">
          {scenarios.error.message}
        </p>
      )}
      {run.isError && (
        <div role="alert" className="mb-4 rounded-control border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          <p className="font-medium">{run.error.message}</p>
          {Object.values(fieldErrorsOf(run.error)).map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}

      {scenarios.isSuccess && scenarios.data.length === 0 && (
        <EmptyState
          icon={FlaskConical}
          title="No scenarios yet"
          message="Ask “what if?” without touching your real data: add an air conditioner, use fewer washes, switch tariff, raise the load limit, or compare scheduling goals."
          action={
            <Button onClick={openNew}>
              <Plus aria-hidden className="size-4" /> Create your first scenario
            </Button>
          }
        />
      )}

      {scenarios.isSuccess && scenarios.data.length > 0 && (
        <div className="space-y-6">
          <ComparisonCard scenarios={scenarios.data} currency={currency} />
          <div className="space-y-4">
            {scenarios.data.map((scenario) => (
              <ScenarioCard
                key={scenario.id}
                scenario={scenario}
                currency={currency}
                timeFormat={timeFormat}
                running={runningId === scenario.id}
                expanded={expandedId === scenario.id}
                onRun={() => runScenario(scenario.id)}
                onEdit={() => setDialog({ kind: 'edit', scenario })}
                onDelete={() => setDialog({ kind: 'delete', scenario })}
                onToggle={() => setExpandedId(expandedId === scenario.id ? null : scenario.id)}
              />
            ))}
          </div>
        </div>
      )}

      {dialog.kind === 'edit' && <ScenarioEditor scenario={dialog.scenario} onClose={close} />}
      {dialog.kind === 'delete' && (
        <ConfirmDialog
          title={`Delete ${dialog.scenario.name}?`}
          message="This removes the scenario and its saved results. Your real household is not affected. This cannot be undone."
          confirmLabel="Delete scenario"
          busy={deletion.isPending}
          error={deletion.isError ? deletion.error.message : null}
          onCancel={close}
          onConfirm={() => deletion.mutate(dialog.scenario.id, { onSuccess: close })}
        />
      )}
    </>
  );
}
