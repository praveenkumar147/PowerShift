import { Plus, ReceiptText } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Spinner } from '@/components/ui/Spinner';
import { useHousehold, useTimeFormat } from '@/features/household/api';
import { useActivateTariff, useDeleteTariff, useTariffs } from '@/features/tariffs/api';
import { TariffFormDialog } from '@/features/tariffs/form/TariffFormDialog';
import { TariffCard } from '@/features/tariffs/TariffCard';
import type { Tariff } from '@/features/tariffs/types';

type DialogState = { kind: 'closed' } | { kind: 'form'; tariff: Tariff | null } | { kind: 'delete'; tariff: Tariff };

export function TariffsPage() {
  const tariffs = useTariffs();
  const currency = useHousehold().data?.currency_code ?? null;
  const timeFormat = useTimeFormat();
  const activate = useActivateTariff();
  const deletion = useDeleteTariff();
  const [dialog, setDialog] = useState<DialogState>({ kind: 'closed' });

  const close = () => {
    deletion.reset();
    setDialog({ kind: 'closed' });
  };
  const openNew = () => setDialog({ kind: 'form', tariff: null });

  return (
    <>
      <PageHeader
        title="Electricity Tariff"
        description="How your electricity is priced. Costs use the active tariff."
        actions={
          <Button onClick={openNew}>
            <Plus aria-hidden className="size-4" /> Add tariff
          </Button>
        }
      />

      {tariffs.isPending && <Spinner label="Loading tariffs" />}
      {tariffs.isError && (
        <p role="alert" className="text-sm text-danger">
          {tariffs.error.message}
        </p>
      )}
      {activate.isError && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {activate.error.message}
        </p>
      )}

      {tariffs.isSuccess && tariffs.data.length === 0 && (
        <EmptyState
          icon={ReceiptText}
          title="No tariff yet"
          message="Add the tariff from your electricity bill. PowerShift never assumes rates from your location."
          action={
            <Button onClick={openNew}>
              <Plus aria-hidden className="size-4" /> Add your tariff
            </Button>
          }
        />
      )}

      {tariffs.isSuccess && tariffs.data.length > 0 && !tariffs.data.some((t) => t.is_active) && (
        <p role="status" className="mb-4 rounded-control border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          No tariff is active, so costs are not calculated. Choose "Use this tariff" on one below.
        </p>
      )}

      <div className="space-y-4">
        {tariffs.data?.map((tariff) => (
          <TariffCard
            key={tariff.id}
            tariff={tariff}
            currency={currency}
            timeFormat={timeFormat}
            activating={activate.isPending}
            onActivate={() => activate.mutate(tariff.id)}
            onEdit={() => setDialog({ kind: 'form', tariff })}
            onDelete={() => setDialog({ kind: 'delete', tariff })}
          />
        ))}
      </div>

      {dialog.kind === 'form' && <TariffFormDialog tariff={dialog.tariff} onClose={close} />}
      {dialog.kind === 'delete' && (
        <ConfirmDialog
          title={`Delete ${dialog.tariff.name}?`}
          message={
            dialog.tariff.is_active
              ? 'This is your active tariff. Costs will not be calculated until you make another tariff active. This cannot be undone.'
              : 'This removes the tariff and all its rates. This cannot be undone.'
          }
          confirmLabel="Delete tariff"
          busy={deletion.isPending}
          error={deletion.isError ? deletion.error.message : null}
          onCancel={close}
          onConfirm={() => deletion.mutate(dialog.tariff.id, { onSuccess: close })}
        />
      )}
    </>
  );
}
