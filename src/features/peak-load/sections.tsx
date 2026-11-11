/** Presentational pieces of the Peak Load page. */
import { AlertTriangle, Info } from 'lucide-react';
import type { ReactNode } from 'react';
import { Card } from '@/components/ui/Card';
import { LinkButton } from '@/components/ui/LinkButton';
import { StatTile } from '@/components/ui/StatTile';
import { WEEKDAY_SHORT } from '@/features/appliances/types';
import type { Contributor, Episode, PeakLoadAnalysis } from '@/features/peak-load/types';
import { formatKw, formatShare } from '@/lib/format';
import { formatWindow, type TimeFormat } from '@/lib/time';

function names(episode: Episode): string {
  return episode.appliances.map((a) => a.name).join(', ');
}

export function PeakTiles({ analysis, timeFormat }: { analysis: PeakLoadAnalysis; timeFormat: TimeFormat }) {
  const firstPeak = analysis.peak_windows[0];
  const limit = analysis.load_limit_kw;
  const headroom = analysis.headroom_kw;
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <StatTile
        label="Peak demand (worst case)"
        value={formatKw(analysis.peak_kw)}
        detail={firstPeak ? `${formatWindow(firstPeak.start_minute, firstPeak.end_minute, timeFormat)} on ${WEEKDAY_SHORT[analysis.weekday]}` : 'No appliances running'}
      />
      <StatTile label="Expected peak" value={formatKw(analysis.peak_expected_kw)} detail="Using duty cycles" />
      <StatTile
        label="Headroom"
        value={headroom === null ? 'No limit set' : headroom < 0 ? `Over by ${formatKw(-headroom)}` : formatKw(headroom)}
        detail={limit === null ? 'Set a load limit in Settings' : `Load limit ${formatKw(limit)}`}
      />
      <StatTile label="Time over limit" value={limit === null ? '—' : analysis.minutes_over_limit ? `${analysis.minutes_over_limit} min` : 'None'} />
    </div>
  );
}

export function LimitAlerts({ analysis, timeFormat }: { analysis: PeakLoadAnalysis; timeFormat: TimeFormat }) {
  const limit = analysis.load_limit_kw;
  if (limit === null) {
    return (
      <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface-raised px-4 py-3 text-sm">
        <span className="flex items-center gap-2 text-muted">
          <Info aria-hidden className="size-4" /> No household load limit is set, so overloads can't be checked.
        </span>
        <LinkButton to="/settings">Set load limit</LinkButton>
      </div>
    );
  }
  if (analysis.violations.length === 0) return null;
  return (
    <div role="alert" className="rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm">
      <p className="flex items-center gap-2 font-medium text-danger">
        <AlertTriangle aria-hidden className="size-4" />
        Load limit exceeded on {WEEKDAY_SHORT[analysis.weekday]} ({formatKw(limit)} limit)
      </p>
      <ul className="mt-2 space-y-1 pl-6 text-fg">
        {analysis.violations.map((v) => (
          <li key={v.start_minute}>
            <span className="font-medium tabular-nums">{formatWindow(v.start_minute, v.end_minute, timeFormat)}</span>: up to {formatKw(v.max_kw)},{' '}
            {formatKw(v.max_kw - limit)} over. Running: {names(v)}.
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PeakContributors({ contributors, peakKw }: { contributors: Contributor[]; peakKw: number }) {
  return (
    <Card title="At the peak" description="Appliances running at the moment of highest demand, at full power.">
      {contributors.length === 0 ? (
        <p className="text-sm text-muted">Nothing is running.</p>
      ) : (
        <table className="w-full text-sm tabular-nums">
          <caption className="sr-only">Appliances contributing to the peak</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">Appliance</th>
              <th scope="col">Share of peak</th>
              <th scope="col">Power</th>
            </tr>
          </thead>
          <tbody>
            {contributors.map((c) => (
              <tr key={c.appliance_id}>
                <th scope="row" className="w-2/5 py-1.5 pr-3 text-left font-normal">
                  {c.name}
                  <span className="block text-xs text-muted">{c.mode === 'flexible' ? 'Flexible' : 'Fixed'}</span>
                </th>
                <td className="py-1.5 pr-3">
                  <div className="h-2 rounded-full bg-surface-raised" role="img" aria-label={`${formatShare(c.kw / peakKw)} of peak`}>
                    <div className="h-2 rounded-full" style={{ width: `${(c.kw / peakKw) * 100}%`, background: c.mode === 'flexible' ? 'var(--ps-series-2)' : 'var(--ps-series-1)' }} />
                  </div>
                </td>
                <td className="w-20 py-1.5 text-right">{formatKw(c.kw)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

interface EpisodeListProps {
  title: string;
  description: string;
  episodes: Episode[];
  empty: string;
  timeFormat: TimeFormat;
  footer?: ReactNode;
}

export function EpisodeList({ title, description, episodes, empty, timeFormat, footer }: EpisodeListProps) {
  return (
    <Card title={title} description={description}>
      {episodes.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="divide-y divide-border text-sm">
          {episodes.map((e) => (
            <li key={e.start_minute} className="py-2">
              <div className="flex justify-between gap-4 tabular-nums">
                <span className="font-medium">{formatWindow(e.start_minute, e.end_minute, timeFormat)}</span>
                <span>up to {formatKw(e.max_kw)}</span>
              </div>
              <p className="text-xs text-muted">{names(e)}</p>
            </li>
          ))}
        </ul>
      )}
      {footer && episodes.length > 0 && <p className="mt-3 text-xs text-muted">{footer}</p>}
    </Card>
  );
}
