import { Plug, Plus, SearchX } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Spinner } from '@/components/ui/Spinner';
import { useAppliances, useDeleteAppliance } from '@/features/appliances/api';
import { ApplianceFiltersBar } from '@/features/appliances/ApplianceFiltersBar';
import { ApplianceTable } from '@/features/appliances/ApplianceTable';
import { ApplianceFormDialog } from '@/features/appliances/form/ApplianceFormDialog';
import type { Appliance, ApplianceFilters } from '@/features/appliances/types';
import { useTimeFormat } from '@/features/household/api';

const NO_FILTERS: ApplianceFilters = { search: '', category: '', mode: '' };

type DialogState = { kind: 'closed' } | { kind: 'form'; appliance: Appliance | null } | { kind: 'delete'; appliance: Appliance };

export function AppliancesPage() {
  const [filters, setFilters] = useState<ApplianceFilters>(NO_FILTERS);
  // Typing updates the box immediately; the query follows without blocking input.
  const deferredFilters = useDeferredValue(filters);
  const appliances = useAppliances(deferredFilters);
  const timeFormat = useTimeFormat();
  const [dialog, setDialog] = useState<DialogState>({ kind: 'closed' });
  const deletion = useDeleteAppliance();

  const filtersActive = filters.search !== '' || filters.category !== '' || filters.mode !== '';
  const closeDialog = () => {
    deletion.reset();
    setDialog({ kind: 'closed' });
  };
  const openNew = () => setDialog({ kind: 'form', appliance: null });

  return (
    <>
      <PageHeader
        title="Appliances"
        description="The appliances in your home and how you use them."
        actions={
          <Button onClick={openNew}>
            <Plus aria-hidden className="size-4" /> Add appliance
          </Button>
        }
      />

      {(filtersActive || (appliances.data?.length ?? 0) > 0) && <ApplianceFiltersBar filters={filters} onChange={setFilters} />}

      {appliances.isPending && <Spinner label="Loading appliances" />}

      {appliances.isError && (
        <div role="alert" className="flex items-center gap-3 text-sm text-danger">
          {appliances.error.message}
          <Button variant="secondary" onClick={() => void appliances.refetch()}>
            Try again
          </Button>
        </div>
      )}

      {appliances.isSuccess && appliances.data.length === 0 && !filtersActive && (
        <EmptyState
          icon={Plug}
          title="No appliances yet"
          message="Add the appliances in your home. Fixed ones (fridge, router) form your baseline; flexible ones (washing machine) can be rescheduled later."
          action={
            <Button onClick={openNew}>
              <Plus aria-hidden className="size-4" /> Add your first appliance
            </Button>
          }
        />
      )}

      {appliances.isSuccess && appliances.data.length === 0 && filtersActive && (
        <EmptyState
          icon={SearchX}
          title="No matching appliances"
          message="Try a different search or filter."
          action={
            <Button variant="secondary" onClick={() => setFilters(NO_FILTERS)}>
              Clear filters
            </Button>
          }
        />
      )}

      {appliances.isSuccess && appliances.data.length > 0 && (
        <>
          <ApplianceTable
            appliances={appliances.data}
            timeFormat={timeFormat}
            onEdit={(appliance) => setDialog({ kind: 'form', appliance })}
            onDelete={(appliance) => setDialog({ kind: 'delete', appliance })}
          />
          <p className="mt-3 text-xs text-muted">
            Estimates, not measurements: energy per day = rated power × quantity × duty cycle × hours on.
          </p>
        </>
      )}

      {dialog.kind === 'form' && <ApplianceFormDialog appliance={dialog.appliance} onClose={closeDialog} />}

      {dialog.kind === 'delete' && (
        <ConfirmDialog
          title={`Delete ${dialog.appliance.name}?`}
          message="This removes the appliance and its usage settings. This cannot be undone."
          confirmLabel="Delete appliance"
          busy={deletion.isPending}
          error={deletion.isError ? deletion.error.message : null}
          onCancel={closeDialog}
          onConfirm={() => deletion.mutate(dialog.appliance.id, { onSuccess: closeDialog })}
        />
      )}
    </>
  );
}
