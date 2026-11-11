import { Link } from 'react-router';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useOptimizationHistory } from '@/features/scheduler/api';
import { PRIORITY_LABELS } from '@/features/scheduler/types';
import { useBackups } from '@/features/settings/api';
import { useScenarios } from '@/features/simulation/api';
import { formatDateTime } from '@/lib/dates';
import { formatKw, formatSignedMoney } from '@/lib/format';

const linkClass = 'text-sm font-medium text-accent underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent';

function Failed({ message }: { message: string }) {
  return (
    <p role="alert" className="text-sm text-danger">
      {message}
    </p>
  );
}

/** The most recent Smart Scheduler run, described only as strongly as it was proven. */
export function SchedulerCard({ currency }: { currency: string | null }) {
  const history = useOptimizationHistory();
  const latest = history.data?.at(0);

  return (
    <Card title="Smart Scheduler" description="Your latest optimization run">
      {history.isPending && <Spinner label="Loading the latest run" />}
      {history.isError && <Failed message={history.error.message} />}
      {history.isSuccess && !latest && (
        <>
          <p className="text-sm text-muted">No optimization has been run yet. The scheduler recommends when to run flexible appliances.</p>
          <Link to="/scheduler" className={`${linkClass} mt-3 inline-block`}>
            Open Smart Scheduler
          </Link>
        </>
      )}
      {latest && (
        <div className="space-y-2 text-sm">
          <p className="text-muted">
            {formatDateTime(latest.created_at)} · goal: {PRIORITY_LABELS[latest.priority].toLowerCase()}
          </p>
          {latest.schedule_valid && latest.baseline_bill !== null && latest.optimized_bill !== null ? (
            <>
              <p>
                Estimated bill change:{' '}
                <strong>{formatSignedMoney(latest.optimized_bill - latest.baseline_bill, currency)}</strong> per month, moving {latest.moved_count} appliance
                {latest.moved_count === 1 ? '' : 's'}.
              </p>
              {latest.optimized_peak_kw !== null && (
                <p>
                  Peak {formatKw(latest.baseline_peak_kw)} → {formatKw(latest.optimized_peak_kw)}.
                </p>
              )}
              <p className="text-muted">{latest.status === 'OPTIMAL' ? 'Proven optimal for the model.' : 'Valid, but not proven optimal.'}</p>
            </>
          ) : (
            <p>No valid schedule was found in this run ({latest.status}). Open the scheduler for the reasons.</p>
          )}
          <Link to="/scheduler" className={`${linkClass} inline-block`}>
            Open Smart Scheduler
          </Link>
        </div>
      )}
    </Card>
  );
}

/** How many what-if scenarios exist, and the most recent comparison. */
export function SimulationCard({ currency }: { currency: string | null }) {
  const scenarios = useScenarios();
  const withResult = (scenarios.data ?? []).filter((s) => s.latest_result !== null);
  const latest = [...withResult].sort((a, b) => (b.latest_result?.created_at ?? '').localeCompare(a.latest_result?.created_at ?? '')).at(0);
  const result = latest?.latest_result;

  return (
    <Card title="Simulation Lab" description="What-if scenarios (your real data is never changed)">
      {scenarios.isPending && <Spinner label="Loading scenarios" />}
      {scenarios.isError && <Failed message={scenarios.error.message} />}
      {scenarios.isSuccess && scenarios.data.length === 0 && (
        <>
          <p className="text-sm text-muted">No scenarios yet. Try adding an appliance or another tariff and compare the bill.</p>
          <Link to="/simulation" className={`${linkClass} mt-3 inline-block`}>
            Open Simulation Lab
          </Link>
        </>
      )}
      {scenarios.isSuccess && scenarios.data.length > 0 && (
        <div className="space-y-2 text-sm">
          <p>
            {scenarios.data.length} scenario{scenarios.data.length === 1 ? '' : 's'}, {withResult.length} with results.
          </p>
          {latest && result ? (
            <p>
              Latest: <strong>{latest.name}</strong>
              {result.bill_change !== null ? (
                <>
                  , {formatSignedMoney(result.bill_change, currency)} per month versus today{latest.result_is_stale ? ' (edited since; run it again)' : ''}.
                </>
              ) : (
                '.'
              )}
            </p>
          ) : (
            <p className="text-muted">None has been run yet.</p>
          )}
          <Link to="/simulation" className={`${linkClass} inline-block`}>
            Open Simulation Lab
          </Link>
        </div>
      )}
    </Card>
  );
}

/** Reminds the user to back up, based on the backups that really exist. */
export function BackupCard() {
  const backups = useBackups();
  const manual = (backups.data ?? []).filter((b) => b.kind === 'manual');
  const latest = manual.at(0);

  return (
    <Card title="Your data" description="Stored only on this computer">
      {backups.isPending && <Spinner label="Loading backups" />}
      {backups.isError && <Failed message={backups.error.message} />}
      {backups.isSuccess && (
        <div className="space-y-2 text-sm">
          {latest ? (
            <p>Last backup you made: {formatDateTime(latest.created_at)}.</p>
          ) : (
            <p>You have not made a backup yet. A backup lets you undo a mistake or move to another computer.</p>
          )}
          <p className="text-muted">
            {backups.data.length} file{backups.data.length === 1 ? '' : 's'} in the backups folder.
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <Link to="/settings" className={linkClass}>
              Backups and data
            </Link>
            <Link to="/reports" className={linkClass}>
              Reports
            </Link>
          </div>
        </div>
      )}
    </Card>
  );
}
