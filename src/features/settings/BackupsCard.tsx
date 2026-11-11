import { Download, FileUp, History, Plus } from 'lucide-react';
import { useRef, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useBackups, useCreateBackup, useDownloadBackup } from '@/features/settings/api';
import { RestoreDialog } from '@/features/settings/RestoreDialog';
import { BACKUP_KIND_LABELS, type RestoreSource } from '@/features/settings/types';
import { formatDateTime } from '@/lib/dates';
import { formatBytes } from '@/lib/download';

export function BackupsCard() {
  const backups = useBackups();
  const create = useCreateBackup();
  const download = useDownloadBackup();
  const [source, setSource] = useState<RestoreSource | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const nextId = useRef(0);

  function onFilePicked(files: FileList | null) {
    const file = files?.[0];
    if (file) setSource({ kind: 'file', file, id: ++nextId.current });
    if (picker.current) picker.current.value = ''; // so picking the same file again still fires
  }

  return (
    <Card
      title="Backups"
      description="A backup is a complete copy of your data. PowerShift also makes a copy automatically before an upgrade, a restore or a reset."
    >
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          <Plus aria-hidden className="size-4" /> {create.isPending ? 'Creating…' : 'Create backup'}
        </Button>
        <Button variant="secondary" onClick={() => picker.current?.click()}>
          <FileUp aria-hidden className="size-4" /> Restore from a file…
        </Button>
        <input ref={picker} type="file" accept=".db,application/octet-stream" className="sr-only" aria-label="Backup file to restore" tabIndex={-1} onChange={(e) => onFilePicked(e.target.files)} />
        {create.isSuccess && (
          <span role="status" className="text-sm text-success">
            Backup created: {create.data.name}
          </span>
        )}
      </div>
      {create.isError && (
        <p role="alert" className="mb-3 text-sm text-danger">
          {create.error.message}
        </p>
      )}
      {download.isError && (
        <p role="alert" className="mb-3 text-sm text-danger">
          {download.error.message}
        </p>
      )}

      {backups.isPending && <Spinner label="Loading backups" />}
      {backups.isError && (
        <p role="alert" className="text-sm text-danger">
          {backups.error.message}
        </p>
      )}
      {backups.isSuccess && backups.data.length === 0 && (
        <p className="flex items-center gap-2 text-sm text-muted">
          <History aria-hidden className="size-4" /> No backups yet. Create one before making big changes.
        </p>
      )}
      {backups.isSuccess && backups.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm tabular-nums">
            <caption className="sr-only">Backups, newest first</caption>
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="py-2 pr-4 font-medium">Created</th>
                <th scope="col" className="py-2 pr-4 font-medium">Kind</th>
                <th scope="col" className="py-2 pr-4 font-medium">Size</th>
                <th scope="col" className="py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {backups.data.map((backup) => (
                <tr key={backup.name}>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {formatDateTime(backup.created_at)}
                    <span className="block font-mono text-xs text-muted">{backup.name}</span>
                  </td>
                  <td className="py-2 pr-4">
                    <Badge tone={backup.kind === 'manual' ? 'accent' : 'neutral'}>{BACKUP_KIND_LABELS[backup.kind]}</Badge>
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap">{formatBytes(backup.size_bytes)}</td>
                  <td className="py-2">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" aria-label={`Download ${backup.name}`} onClick={() => download.mutate(backup.name)}>
                        <Download aria-hidden className="size-4" />
                      </Button>
                      <Button variant="secondary" aria-label={`Restore ${backup.name}`} onClick={() => setSource({ kind: 'stored', name: backup.name })}>
                        Restore
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {source && <RestoreDialog source={source} onClose={() => setSource(null)} />}
    </Card>
  );
}
