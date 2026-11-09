import { Gauge } from 'lucide-react';
import { useState } from 'react';
import { ChartCard, DataTable } from '@/components/charts/ChartCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { LinkButton } from '@/components/ui/LinkButton';
import { NotesBox } from '@/components/ui/NotesBox';
import { PageHeader } from '@/components/ui/PageHeader';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Spinner } from '@/components/ui/Spinner';
import { WEEKDAY_SHORT } from '@/features/appliances/types';
import { useTimeFormat } from '@/features/household/api';
import { usePeakLoad } from '@/features/peak-load/api';
import { LoadProfileChart } from '@/features/peak-load/charts/LoadProfileChart';
import { WeeklyPeakChart } from '@/features/peak-load/charts/WeeklyPeakChart';
import { EpisodeList, LimitAlerts, PeakContributors, PeakTiles } from '@/features/peak-load/sections';
import type { PeakLoadAnalysis } from '@/features/peak-load/types';
import { formatKw } from '@/lib/format';
import { formatMinute, formatWindow, type TimeFormat } from '@/lib/time';

const DAY_OPTIONS = WEEKDAY_SHORT.map((label, i) => ({ value: String(i), label }));
const STEPS_PER_HOUR = 4;

export function PeakLoadPage() {
  // null = let the backend pick the day with the highest peak.
  const [weekday, setWeekday] = useState<number | null>(null);
  const analysis = usePeakLoad(weekday);
  const timeFormat = useTimeFormat();

  return (
    <>
      <PageHeader title="Peak Load" description="How hard your household pushes its electricity connection through the day (kW)." />
      {analysis.isPending && <Spinner label="Analysing demand" />}
      {analysis.isError && (
        <p role="alert" className="text-sm text-danger">
          {analysis.error.message}
        </p>
      )}
      {analysis.data && analysis.data.appliances.length === 0 && (
        <EmptyState icon={Gauge} title="No appliances yet" message="Add appliances to analyse household demand." action={<LinkButton to="/appliances">Add appliances</LinkButton>} />
      )}
      {analysis.data && analysis.data.appliances.length > 0 && (
        <PeakLoadView analysis={analysis.data} timeFormat={timeFormat} onSelectDay={setWeekday} />
      )}
    </>
  );
}

function PeakLoadView({ analysis, timeFormat, onSelectDay }: { analysis: PeakLoadAnalysis; timeFormat: TimeFormat; onSelectDay: (day: number) => void }) {
  const hourly = Array.from({ length: 24 }, (_, hour) => {
    const steps = analysis.steps.slice(hour * STEPS_PER_HOUR, (hour + 1) * STEPS_PER_HOUR);
    return {
      hour,
      worst: Math.max(...steps.map((s) => s.worst_kw)),
      expected: Math.max(...steps.map((s) => s.expected_kw)),
    };
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium">
          Day analysed
        </span>
        <div className="w-full max-w-md">
          <SegmentedControl label="Day analysed" size="sm" options={DAY_OPTIONS} value={String(analysis.weekday)} onChange={(v) => onSelectDay(Number(v))} />
        </div>
        {analysis.selected_automatically && <span className="text-xs text-muted">Showing the day with the highest peak</span>}
      </div>

      <PeakTiles analysis={analysis} timeFormat={timeFormat} />
      <LimitAlerts analysis={analysis} timeFormat={timeFormat} />

      <ChartCard
        title="24-hour load profile"
        description="Worst-case demand in 15-minute steps: every appliance that is on draws full power. Hover to see what is running."
        table={
          <DataTable
            caption="Highest demand in each hour"
            columns={['Hour', 'Worst case', 'Expected']}
            rows={hourly.map((h) => [formatWindow(h.hour * 60, (h.hour + 1) * 60, timeFormat), formatKw(h.worst), formatKw(h.expected)])}
          />
        }
      >
        <LoadProfileChart steps={analysis.steps} appliances={analysis.appliances} limitKw={analysis.load_limit_kw} timeFormat={timeFormat} />
        <p className="mt-3 text-xs text-muted">
          At the peak: {formatKw(analysis.peak_fixed_kw)} fixed + {formatKw(analysis.peak_flexible_kw)} flexible. Only the flexible part can be
          rescheduled.
        </p>
      </ChartCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <PeakContributors contributors={analysis.peak_contributors} peakKw={analysis.peak_kw} />
        <ChartCard
          title="Peak by day"
          description="Click a day to analyse it."
          table={
            <DataTable
              caption="Peak demand by weekday"
              columns={['Day', 'Peak', 'Starts', ...(analysis.load_limit_kw !== null ? ['Over limit'] : [])]}
              rows={analysis.week.map((d) => [
                WEEKDAY_SHORT[d.weekday] ?? '',
                formatKw(d.peak_kw),
                formatMinute(d.peak_start_minute, timeFormat),
                ...(analysis.load_limit_kw !== null ? [d.minutes_over_limit ? `${d.minutes_over_limit} min` : 'No'] : []),
              ])}
            />
          }
        >
          <WeeklyPeakChart week={analysis.week} limitKw={analysis.load_limit_kw} selected={analysis.weekday} onSelect={onSelectDay} timeFormat={timeFormat} />
        </ChartCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <EpisodeList
          title="High-demand periods"
          description={analysis.load_limit_kw !== null ? 'At least 80% of the load limit.' : "At least 80% of the day's peak."}
          episodes={analysis.high_demand}
          empty="None."
          timeFormat={timeFormat}
        />
        <EpisodeList
          title="Heavy appliances overlapping"
          description="Two or more appliances of 1 kW or more on at once."
          episodes={analysis.overlaps}
          empty="No heavy appliances overlap."
          timeFormat={timeFormat}
        />
        <EpisodeList
          title="Not allowed together"
          description="Appliances you marked as not running simultaneously, overlapping at their usual times."
          episodes={analysis.conflicts}
          empty="No conflicts."
          timeFormat={timeFormat}
          footer="The Smart Scheduler (Stage 5) will separate these."
        />
      </div>

      <NotesBox notes={analysis.notes} />
    </div>
  );
}
