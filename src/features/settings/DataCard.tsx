import { CheckCircle2, FileJson, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { TextInput } from '@/components/ui/inputs';
import { Modal } from '@/components/ui/Modal';
import { useExportData, useResetData } from '@/features/settings/api';

const CONFIRM_WORD = 'RESET';

const REMOVED_LABELS: Record<string, string> = {
  household: 'household profile',
  appliances: 'appliances',
  tariffs: 'tariffs',
  simulation_scenarios: 'scenarios',
  optimization_runs: 'optimization runs',
};

/** Deleting everything needs a typed confirmation, and a safety backup is made first. */
function ResetDialog({ onClose }: { onClose: () => void }) {
  const [typed, setTyped] = useState('');
  const reset = useResetData();
  const done = reset.data;

  return (
    <Modal
      title="Delete all data?"
      description="This removes your household, appliances, tariffs, scenarios and optimization history."
      onClose={onClose}
      footer={
        done ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose} data-autofocus>
              Cancel
            </Button>
            <Button variant="danger" disabled={typed !== CONFIRM_WORD || reset.isPending} onClick={() => reset.mutate()}>
              {reset.isPending ? 'Deleting…' : 'Delete all data'}
            </Button>
          </>
        )
      }
    >
      {!done && (
        <div className="space-y-4 text-sm">
          <p>
            A backup of your current data is saved first, so you can restore it afterwards. Existing backups are kept.
          </p>
          <Field label={`Type ${CONFIRM_WORD} to confirm`}>
            {(p) => <TextInput {...p} value={typed} autoComplete="off" spellCheck={false} onChange={(e) => setTyped(e.target.value)} />}
          </Field>
          {reset.isError && (
            <p role="alert" className="text-danger">
              {reset.error.message}
            </p>
          )}
        </div>
      )}
      {done && (
        <div role="status" className="space-y-2 text-sm">
          <p className="flex items-center gap-2 font-medium text-success">
            <CheckCircle2 aria-hidden className="size-4" /> All data was deleted.
          </p>
          <p className="text-muted">
            Removed: {Object.entries(done.removed).map(([key, count]) => `${count} ${REMOVED_LABELS[key] ?? key}`).join(', ')}.
          </p>
          <p>
            Your data was saved first as <span className="font-mono text-xs">{done.safety_backup.name}</span>. Restore that backup to bring it back.
          </p>
        </div>
      )}
    </Modal>
  );
}

export function DataCard() {
  const exportData = useExportData();
  const [resetting, setResetting] = useState(false);

  return (
    <Card title="Your data" description="Export a readable copy, or start again with an empty PowerShift.">
      <div className="divide-y divide-border">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
          <div>
            <p className="text-sm font-medium">Export data</p>
            <p className="text-xs text-muted">A JSON file with your household, appliances, tariffs and scenarios, for archiving or analysis. To move or restore your data, use a backup.</p>
          </div>
          <Button variant="secondary" onClick={() => exportData.mutate()} disabled={exportData.isPending}>
            <FileJson aria-hidden className="size-4" /> {exportData.isPending ? 'Preparing…' : 'Export data'}
          </Button>
        </div>
        {exportData.isSuccess && (
          <p role="status" className="py-2 text-sm text-success">
            Download started: {exportData.data}
          </p>
        )}
        {exportData.isError && (
          <p role="alert" className="py-2 text-sm text-danger">
            {exportData.error.message}
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
          <div>
            <p className="text-sm font-medium text-danger">Delete all data</p>
            <p className="text-xs text-muted">Removes everything you entered. A backup is made first.</p>
          </div>
          <Button variant="danger" onClick={() => setResetting(true)}>
            <Trash2 aria-hidden className="size-4" /> Delete all data…
          </Button>
        </div>
      </div>
      {resetting && <ResetDialog onClose={() => setResetting(false)} />}
    </Card>
  );
}
