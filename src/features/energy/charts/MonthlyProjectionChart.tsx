import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DataTable } from '@/components/charts/ChartCard';
import { AxisUnit, AXIS_PROPS, BAR_RADIUS_TOP, GRID_PROPS, SERIES, TOOLTIP_CURSOR, TooltipBox } from '@/components/charts/chartTheme';
import type { MonthRow } from '@/features/energy/types';
import { monthLong, monthShort } from '@/lib/dates';
import { formatKwh, formatMoney } from '@/lib/format';

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
}

/** One measure per chart (energy); the bill appears in the tooltip and table, never on a second axis. */
export function MonthlyProjectionChart({ months, currency }: { months: MonthRow[]; currency: string | null }) {
  const renderTooltip = ({ active, payload }: TooltipProps) => {
    const row = payload?.[0]?.payload as MonthRow | undefined;
    if (!active || !row) return null;
    const rows = [
      { label: 'Energy', value: formatKwh(row.kwh), color: SERIES.primary },
      { label: 'Days', value: String(row.days) },
    ];
    if (row.bill_total !== null) rows.push({ label: 'Estimated bill', value: formatMoney(row.bill_total, currency) });
    return <TooltipBox title={monthLong(row.month)} rows={rows} />;
  };

  return (
    <>
    <AxisUnit>kWh per month</AxisUnit>
    <div className="h-64" role="img" aria-label="Bar chart of estimated energy per month">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={months} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="month" {...AXIS_PROPS} tickFormatter={monthShort} />
          <YAxis {...AXIS_PROPS} width={44} />
          <Tooltip cursor={TOOLTIP_CURSOR} content={renderTooltip} />
          <Bar dataKey="kwh" fill={SERIES.primary} radius={BAR_RADIUS_TOP} maxBarSize={28} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
    </>
  );
}

export function MonthlyProjectionTable({ months, currency }: { months: MonthRow[]; currency: string | null }) {
  const priced = months.some((m) => m.bill_total !== null);
  return (
    <DataTable
      caption="Estimated energy and bill per month"
      columns={['Month', 'Days', 'Energy', ...(priced ? ['Estimated bill'] : [])]}
      rows={months.map((m) => [
        monthLong(m.month),
        m.days,
        formatKwh(m.kwh),
        ...(priced ? [formatMoney(m.bill_total ?? 0, currency)] : []),
      ])}
    />
  );
}
