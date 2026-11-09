import { CheckCircle2, XCircle } from 'lucide-react';
import { useHealth } from '@/api/health';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';

/** Shows real data from GET /api/health, proving UI → backend → database works. */
export function SystemStatusCard() {
  const health = useHealth();

  return (
    <Card title="Local engine" description="Backend and database status">
      {health.isPending && <Spinner label="Checking backend" />}

      {health.isError && (
        <div className="space-y-3">
          <p className="flex items-center gap-2 text-sm font-medium text-danger" role="alert">
            <XCircle aria-hidden className="size-4" />
            {health.error.message}
          </p>
          <Button variant="secondary" onClick={() => void health.refetch()}>
            Check again
          </Button>
        </div>
      )}

      {health.isSuccess && (
        <div className="space-y-4">
          <p className="flex items-center gap-2 text-sm font-medium text-success">
            <CheckCircle2 aria-hidden className="size-4" />
            Backend connected
          </p>
          <dl className="space-y-3 text-sm">
            <StatusRow label="Version" value={health.data.version} />
            <StatusRow label="Database schema" value={health.data.schema_revision ?? 'not initialised'} />
            <StatusRow label="Database file" value={health.data.database_path} mono />
          </dl>
        </div>
      )}
    </Card>
  );
}

function StatusRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className={mono ? 'mt-0.5 break-all font-mono text-xs' : 'mt-0.5'}>{value}</dd>
    </div>
  );
}
