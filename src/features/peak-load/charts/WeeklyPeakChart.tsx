import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AxisUnit, AXIS_PROPS, BAR_RADIUS_TOP, GRID_PROPS, niceCeiling, SERIES, TOOLTIP_CURSOR, TooltipBox } from '@/components/charts/chartTheme';
import { WEEKDAY_SHORT } from '@/features/appliances/types';
import type { DaySummary } from '@/features/peak-load/types';
import { formatKw } from '@/lib/format';
import { formatMinute, type TimeFormat } from '@/lib/time';

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
}

interface WeeklyPeakChartProps {
  week: DaySummary[];
  limitKw: number | null;
  selected: number;
  onSelect: (weekday: number) => void;
  timeFormat: TimeFormat;
}

/** Each weekday's worst-case peak; the selected day is full colour, the others muted. Click a bar to select it. */
export function WeeklyPeakChart({ week, limitKw, selected, onSelect, timeFormat }: WeeklyPeakChartProps) {
  const top = niceCeiling(Math.max(limitKw ?? 0, ...week.map((d) => d.peak_kw)) * 1.05);
  const renderTooltip = ({ active, payload }: TooltipProps) => {
    const day = payload?.[0]?.payload as DaySummary | undefined;
    if (!active || !day) return null;
    const rows = [
      { label: 'Peak (worst case)', value: formatKw(day.peak_kw), color: SERIES.primary },
      { label: 'Expected peak', value: formatKw(day.peak_expected_kw) },
      { label: 'Peak starts', value: formatMinute(day.peak_start_minute, timeFormat) },
    ];
    if (limitKw !== null) rows.push({ label: 'Over the limit', value: day.minutes_over_limit ? `${day.minutes_over_limit} min` : 'No' });
    return <TooltipBox title={WEEKDAY_SHORT[day.weekday] ?? ''} rows={rows} />;
  };

  return (
    <>
      <AxisUnit>kW (worst-case peak)</AxisUnit>
      <div className="h-48" role="img" aria-label="Bar chart of each weekday's peak demand">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={week} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="weekday" tickFormatter={(d: number) => WEEKDAY_SHORT[d] ?? ''} {...AXIS_PROPS} />
            <YAxis {...AXIS_PROPS} width={40} domain={[0, top]} tickCount={5} />
            <Tooltip cursor={TOOLTIP_CURSOR} content={renderTooltip} />
            <Bar
              dataKey="peak_kw"
              radius={BAR_RADIUS_TOP}
              maxBarSize={36}
              isAnimationActive={false}
              cursor="pointer"
              onClick={(_, index) => onSelect(week[index]?.weekday ?? selected)}
            >
              {week.map((day) => (
                <Cell key={day.weekday} fill={SERIES.primary} fillOpacity={day.weekday === selected ? 1 : 0.4} />
              ))}
            </Bar>
            {limitKw !== null && <ReferenceLine y={limitKw} stroke="var(--ps-danger)" strokeDasharray="6 4" strokeWidth={2} />}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}
