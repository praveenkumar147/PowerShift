import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DataTable } from '@/components/charts/ChartCard';
import { AxisUnit, AXIS_PROPS, BAR_RADIUS_TOP, GRID_PROPS, SERIES, TOOLTIP_CURSOR, TooltipBox, chartMotion } from '@/components/charts/chartTheme';
import type { DayRow } from '@/features/energy/types';
import { formatDayLong, formatDayShort } from '@/lib/dates';
import { formatKwh, formatMoney } from '@/lib/format';

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
}

export function DailyEnergyChart({ daily, currency }: { daily: DayRow[]; currency: string | null }) {
  const renderTooltip = ({ active, payload }: TooltipProps) => {
    const day = payload?.[0]?.payload as DayRow | undefined;
    if (!active || !day) return null;
    const rows: Array<{ label: string; value: string; color?: string }> = [{ label: 'Energy', value: formatKwh(day.kwh), color: SERIES.highlight }];
    if (day.energy_charge !== null) rows.push({ label: 'Energy charge', value: formatMoney(day.energy_charge, currency) });
    return <TooltipBox title={formatDayLong(day.date)} rows={rows} />;
  };

  return (
    <>
    <AxisUnit>kWh per day</AxisUnit>
    <div className="h-64" role="img" aria-label="Bar chart of estimated energy per day">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={daily} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="date" {...AXIS_PROPS} tickFormatter={formatDayShort} minTickGap={16} />
          <YAxis {...AXIS_PROPS} width={40} />
          <Tooltip cursor={TOOLTIP_CURSOR} content={renderTooltip} />
          <Bar dataKey="kwh" fill={SERIES.highlight} radius={BAR_RADIUS_TOP} maxBarSize={24} {...chartMotion()} />
        </BarChart>
      </ResponsiveContainer>
    </div>
    </>
  );
}

export function DailyEnergyTable({ daily, currency }: { daily: DayRow[]; currency: string | null }) {
  const priced = daily.some((d) => d.energy_charge !== null);
  return (
    <DataTable
      caption="Estimated energy per day"
      columns={priced ? ['Date', 'Energy', 'Energy charge'] : ['Date', 'Energy']}
      rows={daily.map((d) => {
        const row: Array<string | number> = [formatDayLong(d.date), formatKwh(d.kwh)];
        if (priced) row.push(formatMoney(d.energy_charge ?? 0, currency));
        return row;
      })}
    />
  );
}
