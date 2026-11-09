import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AXIS_PROPS, BAR_RADIUS_END, SERIES, TOOLTIP_CURSOR, TooltipBox } from '@/components/charts/chartTheme';
import { formatKwh, formatMoney, formatShare } from '@/lib/format';

export type BreakdownMetric = 'kwh' | 'cost';

export interface BreakdownItem {
  key: string;
  label: string;
  kwh: number;
  share: number;
  energy_charge: number | null;
}

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
}

const ROW_HEIGHT = 32;

interface BreakdownChartProps {
  items: BreakdownItem[];
  metric: BreakdownMetric;
  currency: string | null;
  label: string;
  /** Width reserved for the item names on the left. */
  nameWidth?: number;
}

/**
 * Horizontal bars, largest first: the easiest form for comparing magnitudes
 * across many named items (a pie chart would be harder to read).
 */
export function BreakdownChart({ items, metric, currency, label, nameWidth = 140 }: BreakdownChartProps) {
  const data = items.map((item) => ({ ...item, value: metric === 'kwh' ? item.kwh : (item.energy_charge ?? 0) }));
  const format = (value: number) => (metric === 'kwh' ? formatKwh(value) : formatMoney(value, currency));

  const renderTooltip = ({ active, payload }: TooltipProps) => {
    const item = payload?.[0]?.payload as BreakdownItem | undefined;
    if (!active || !item) return null;
    const rows = [
      { label: 'Energy', value: formatKwh(item.kwh), color: SERIES.primary },
      { label: 'Share of energy', value: formatShare(item.share) },
    ];
    if (item.energy_charge !== null) rows.push({ label: 'Energy charge', value: formatMoney(item.energy_charge, currency) });
    return <TooltipBox title={item.label} rows={rows} />;
  };

  return (
    <div style={{ height: Math.max(ROW_HEIGHT * 2, data.length * ROW_HEIGHT + 8) }} role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 96, bottom: 0, left: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="label" {...AXIS_PROPS} width={nameWidth} />
          <Tooltip cursor={TOOLTIP_CURSOR} content={renderTooltip} />
          <Bar
            dataKey="value"
            fill={SERIES.primary}
            radius={BAR_RADIUS_END}
            maxBarSize={18}
            isAnimationActive={false}
            label={{ position: 'right', fill: 'var(--ps-muted)', fontSize: 12, formatter: (v: unknown) => format(Number(v)) }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
