import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import type { ReactNode } from 'react';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useBillEstimate } from '@/features/energy/api';
import { WEEKDAY_SHORT } from '@/features/appliances/types';
import { usePeakLoad } from '@/features/peak-load/api';
import { formatKw } from '@/lib/format';

type Tone = 'good' | 'warning' | 'info';

function Row({ tone, children }: { tone: Tone; children: ReactNode }) {
  const Icon = tone === 'warning' ? AlertTriangle : tone === 'good' ? CheckCircle2 : Info;
  const color = tone === 'warning' ? 'text-warning' : tone === 'good' ? 'text-accent-ink' : 'text-muted';
  return (
    <li className="flex items-start gap-3 text-sm">
      <Icon aria-hidden className={`mt-0.5 size-4 shrink-0 ${color}`} />
      <span>{children}</span>
    </li>
  );
}

/**
 * Warnings and observations, each derived from real analysis results. Amber is used only when
 * something is actually wrong (a load limit that is exceeded); nothing here is filler.
 */
export function InsightsCard() {
  const peak = usePeakLoad(null);
  const now = new Date();
  const bill = useBillEstimate(now.getFullYear(), now.getMonth() + 1);

  return (
    <Card title="Insights" description="What stands out in your household" index={4} className="h-full">
      {peak.isPending && <Spinner label="Checking your load" />}
      {peak.isError && (
        <p role="alert" className="text-sm text-danger">
          {peak.error.message}
        </p>
      )}
      {peak.data && (
        <ul className="space-y-3">
          {peak.data.load_limit_kw === null ? (
            <Row tone="info">No load limit is set, so peaks cannot be checked. Set one in Settings.</Row>
          ) : peak.data.minutes_over_limit > 0 ? (
            <Row tone="warning">
              Over your {formatKw(peak.data.load_limit_kw)} limit for {peak.data.minutes_over_limit} minutes on {WEEKDAY_SHORT[peak.data.weekday]}, peaking at {formatKw(peak.data.peak_kw)}.
            </Row>
          ) : (
            <Row tone="good">
              Within your {formatKw(peak.data.load_limit_kw)} limit, with {formatKw(peak.data.headroom_kw ?? 0)} to spare at the worst moment.
            </Row>
          )}
          {peak.data.conflicts.length > 0 && (
            <Row tone="warning">
              {peak.data.conflicts.length} time{peak.data.conflicts.length === 1 ? '' : 's'} when appliances that should not run together overlap.
            </Row>
          )}
          {bill.data && bill.data.total === null && <Row tone="info">No tariff is active, so costs are not shown.</Row>}
          {peak.data.peak_flexible_kw > 0 && (
            <Row tone="info">
              {formatKw(peak.data.peak_flexible_kw)} of your peak comes from flexible appliances, which the Smart Scheduler can move.
            </Row>
          )}
        </ul>
      )}
    </Card>
  );
}
