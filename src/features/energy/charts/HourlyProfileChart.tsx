import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DataTable } from '@/components/charts/ChartCard';
import { AXIS_PROPS, BAR_RADIUS_TOP, GRID_PROPS, LegendItem, SERIES, TOOLTIP_CURSOR, TooltipBox } from '@/components/charts/chartTheme';
import type { HourRow } from '@/features/energy/types';
import { formatKwh, formatRate } from '@/lib/format';
import { formatMinute, type TimeFormat } from '@/lib/time';

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
}

interface HourlyProps {
  hours: HourRow[];
  currency: string | null;
  timeFormat: TimeFormat;
  height?: number;
}

function hourLabel(hour: number, format: TimeFormat): string {
  return `${formatMinute(hour * 60, format)}–${formatMinute((hour + 1) * 60, format)}`;
}

/** Stacked bars: fixed (baseline) load and flexible load in each hour of a typical day. */
export function HourlyProfileChart({ hours, currency, timeFormat, height = 256 }: HourlyProps) {
  const renderTooltip = ({ active, payload }: TooltipProps) => {
    const row = payload?.[0]?.payload as HourRow | undefined;
    if (!active || !row) return null;
    const rows = [
      { label: 'Fixed', value: formatKwh(row.fixed_kwh), color: SERIES.primary },
      { label: 'Flexible', value: formatKwh(row.flexible_kwh), color: SERIES.secondary },
      { label: 'Total', value: formatKwh(row.kwh) },
    ];
    if (row.price_per_kwh !== null) rows.push({ label: 'Price', value: formatRate(row.price_per_kwh, currency) });
    return <TooltipBox title={hourLabel(row.hour, timeFormat)} rows={rows} />;
  };

  return (
    <div>
      <div className="mb-2 flex gap-4">
        <LegendItem color={SERIES.primary}>Fixed (baseline)</LegendItem>
        <LegendItem color={SERIES.secondary}>Flexible</LegendItem>
        <span className="ml-auto text-xs text-muted">kWh per hour</span>
      </div>
      <div style={{ height }} role="img" aria-label="Stacked bar chart of estimated energy in each hour, fixed and flexible">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={hours} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="hour" {...AXIS_PROPS} tickFormatter={(h: number) => formatMinute(h * 60, timeFormat)} interval={2} />
            <YAxis {...AXIS_PROPS} width={40} />
            <Tooltip cursor={TOOLTIP_CURSOR} content={renderTooltip} />
            <Bar dataKey="fixed_kwh" stackId="load" fill={SERIES.primary} stroke="var(--ps-surface)" strokeWidth={1} maxBarSize={22} isAnimationActive={false} />
            <Bar dataKey="flexible_kwh" stackId="load" fill={SERIES.secondary} stroke="var(--ps-surface)" strokeWidth={1} radius={BAR_RADIUS_TOP} maxBarSize={22} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function HourlyProfileTable({ hours, currency, timeFormat }: Omit<HourlyProps, 'height'>) {
  const priced = hours.some((h) => h.price_per_kwh !== null);
  return (
    <DataTable
      caption="Estimated energy per hour"
      columns={['Hour', 'Fixed', 'Flexible', 'Total', ...(priced ? ['Price'] : [])]}
      rows={hours.map((h) => [
        hourLabel(h.hour, timeFormat),
        formatKwh(h.fixed_kwh),
        formatKwh(h.flexible_kwh),
        formatKwh(h.kwh),
        ...(priced ? [h.price_per_kwh === null ? '—' : formatRate(h.price_per_kwh, currency)] : []),
      ])}
    />
  );
}
