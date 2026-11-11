import { CheckCircle2, ShieldAlert, XCircle } from 'lucide-react';
import { ApiError, fieldErrorsOf } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { useCheckRestore, useRestore } from '@/features/settings/api';
import type { BackupSummary, RestoreSource } from '@/features/settings/types';
import { formatBytes } from '@/lib/download';

function describeSource(source: RestoreSource): string {
  return source.kind === 'stored' ? source.name : source.file.name;
}

/** Why a backup was rejected, in the backend's own words. */
function rejection(error: unknown): string {
  const fields = fieldErrorsOf(error);
  if (fields.file) return fields.file;
  return error instanceof ApiError ? error.message : 'The file could not be checked.';
}

function Contents({ summary }: { summary: BackupSummary }) {
  const items = [
    summary.household_name ? `Household “${summary.household_name}”` : 'No household profile',
    `${summary.appliances} appliance${summary.appliances === 1 ? '' : 's'}`,
    `${summary.tariffs} tariff${summary.tariffs === 1 ? '' : 's'}`,
    `${summary.scenarios} scenario${summary.scenarios === 1 ? '' : 's'}`,
    `${summary.optimization_runs} optimization run${summary.optimization_runs === 1 ? '' : 's'}`,
  ];
  return (
    <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

interface RestoreDialogProps {
  source: RestoreSource;
  onClose: () => void;
}

/**
 * The backup is checked first; nothing is replaced until the user has seen what it
 * contains and confirmed. A safety copy of the current data is made automatically.
 */
export function RestoreDialog({ source, onClose }: RestoreDialogProps) {
  const check = useCheckRestore(source);
  const restore = useRestore();
  const done = restore.data;

  const footer = done ? (
    <Button onClick={onClose}>Done</Button>
  ) : (
    <>
      <Button variant="secondary" onClick={onClose} data-autofocus>
        {check.isError ? 'OK' : 'Cancel'}
      </Button>
      {check.isSuccess && (
        <Button variant="danger" disabled={restore.isPending} onClick={() => restore.mutate(source)}>
          {restore.isPending ? 'Restoring…' : 'Replace my data'}
        </Button>
      )}
    </>
  );

  return (
    <Modal title="Restore a backup" description={describeSource(source)} onClose={onClose} footer={footer}>
      {check.isPending && (
        <div className="flex items-center gap-3 text-sm text-muted">
          <Spinner label="Checking the backup" /> Checking that the backup is valid…
        </div>
      )}

      {check.isError && (
        <div role="alert" className="flex items-start gap-3 text-sm">
          <XCircle aria-hidden className="mt-0.5 size-5 shrink-0 text-danger" />
          <div>
            <p className="font-medium text-danger">This backup cannot be restored.</p>
            <p className="mt-1">{rejection(check.error)}</p>
            <p className="mt-2 text-muted">Your current data has not been changed.</p>
          </div>
        </div>
      )}

      {check.isSuccess && !done && (
        <div className="space-y-4 text-sm">
          <p className="flex items-center gap-2 font-medium text-success">
            <CheckCircle2 aria-hidden className="size-4" /> The backup is valid ({formatBytes(check.data.size_bytes)}).
          </p>
          <div>
            <p className="font-medium">It contains</p>
            <Contents summary={check.data} />
            {check.data.needs_upgrade && (
              <p className="mt-2 text-muted">It was made by an older version and will be upgraded automatically.</p>
            )}
          </div>
          <p className="flex items-start gap-2 rounded-control border border-warning/30 bg-warning/10 px-3 py-2 text-warning">
            <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
            <span>
              This replaces <strong>all</strong> your current data. A copy of your current data is saved first, so you can undo the restore.
            </span>
          </p>
          {restore.isError && (
            <p role="alert" className="text-danger">
              {rejection(restore.error)}
            </p>
          )}
        </div>
      )}

      {done && (
        <div role="status" className="space-y-2 text-sm">
          <p className="flex items-center gap-2 font-medium text-success">
            <CheckCircle2 aria-hidden className="size-4" /> Your data was restored.
          </p>
          <p>
            Your previous data was saved as <span className="font-mono text-xs">{done.safety_backup.name}</span>. Restore that backup if you want to undo this.
          </p>
        </div>
      )}
    </Modal>
  );
}
