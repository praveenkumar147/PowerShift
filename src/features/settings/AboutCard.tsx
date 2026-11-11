import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useAbout } from '@/features/settings/api';
import { formatBytes } from '@/lib/download';

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid gap-1 py-2 md:grid-cols-[11rem_1fr]">
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className={mono ? 'break-all font-mono text-xs' : 'text-sm'}>{value}</dd>
    </div>
  );
}

const COUNT_LABELS: Record<string, string> = {
  household: 'Household',
  appliances: 'Appliances',
  tariffs: 'Tariffs',
  simulation_scenarios: 'Scenarios',
  optimization_runs: 'Optimization runs',
};

export function AboutCard() {
  const about = useAbout();
  return (
    <Card title="About and storage" description="PowerShift works entirely offline. Your data is stored in one file on this computer.">
      {about.isPending && <Spinner label="Loading" />}
      {about.isError && (
        <p role="alert" className="text-sm text-danger">
          {about.error.message}
        </p>
      )}
      {about.data && (
        <dl className="divide-y divide-border">
          <Row label="Version" value={`PowerShift ${about.data.app_version}`} />
          <Row label="Database schema" value={about.data.schema_revision ?? 'not initialised'} />
          <Row label="Optimization engine" value={about.data.solver} />
          <Row label="Python" value={about.data.python_version} />
          <Row label="Database file" value={about.data.database_path} mono />
          <Row label="Database size" value={formatBytes(about.data.database_size_bytes)} />
          <Row label="Backups folder" value={about.data.backups_dir} mono />
          <Row label="Log files" value={about.data.logs_dir} mono />
          <Row
            label="Stored data"
            value={Object.entries(about.data.counts)
              .map(([key, count]) => `${COUNT_LABELS[key] ?? key}: ${count}`)
              .join(' · ')}
          />
        </dl>
      )}
    </Card>
  );
}
