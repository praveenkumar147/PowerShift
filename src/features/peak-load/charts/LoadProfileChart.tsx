import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AxisUnit, AXIS_PROPS, GRID_PROPS, LegendItem, niceCeiling, SERIES, TooltipBox, chartMotion } from '@/components/charts/chartTheme';
import type { ApplianceInfo, DemandStep } from '@/features/peak-load/types';
import { formatKw } from '@/lib/format';
import { formatMinute, formatWindow, type TimeFormat } from '@/lib/time';

const STEP_MINUTES = 15;
const HOUR_TICKS = [0, 180, 360, 540, 720, 900, 1080, 1260];
const HEADROOM_FACTOR = 1.05;
const LIMIT_COLOR = 'var(--ps-danger)';

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
}

interface LoadProfileChartProps {
  steps: DemandStep[];
  appliances: ApplianceInfo[];
  limitKw: number | null;
  timeFormat: TimeFormat;
  /** Force the y-axis to cover at least this value, so two charts can share a scale. */
  scaleToKw?: number;
  compact?: boolean;
}

/**
 * Worst-case demand through the day in 15-minute steps, stacked fixed + flexible,
 * with the household load limit as a dashed line. Step-shaped areas, because demand
 * changes in jumps when appliances switch on and off.
 */
export function LoadProfileChart({ steps, appliances, limitKw, timeFormat, scaleToKw = 0, compact = false }: LoadProfileChartProps) {
  const names = new Map(appliances.map((a) => [a.appliance_id, a.name]));
  const peak = Math.max(0, ...steps.map((s) => s.worst_kw));
  const top = niceCeiling(Math.max(peak, limitKw ?? 0, scaleToKw) * HEADROOM_FACTOR);

  const renderTooltip = ({ active, payload }: TooltipProps) => {
    const step = payload?.[0]?.payload as DemandStep | undefined;
    if (!active || !step) return null;
    const running = step.appliance_ids.map((id) => names.get(id) ?? `#${id}`);
    return (
      <div>
        <TooltipBox
          title={formatWindow(step.start_minute, step.start_minute + STEP_MINUTES, timeFormat)}
          rows={[
            { label: 'Fixed', value: formatKw(step.fixed_kw), color: SERIES.primary },
            { label: 'Flexible', value: formatKw(step.flexible_kw), color: SERIES.secondary },
            { label: 'Worst case', value: formatKw(step.worst_kw) },
            { label: 'Expected', value: formatKw(step.expected_kw) },
          ]}
        />
        {running.length > 0 && (
          <p className="mt-1 max-w-56 rounded-control border border-border bg-surface px-3 py-1.5 text-xs text-muted shadow-lg">
            On: {running.join(', ')}
          </p>
        )}
      </div>
    );
  };

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-4">
        <LegendItem color={SERIES.primary}>Fixed (baseline)</LegendItem>
        <LegendItem color={SERIES.secondary}>Flexible</LegendItem>
        {limitKw !== null && (
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <span aria-hidden className="inline-block w-4 border-t-2 border-dashed" style={{ borderColor: LIMIT_COLOR }} />
            Load limit {formatKw(limitKw)}
          </span>
        )}
      </div>
      <AxisUnit>kW (worst case)</AxisUnit>
      <div className={compact ? 'h-48' : 'h-72'} role="img" aria-label="Step chart of worst-case household demand through the day, with the load limit">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={steps} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis
              dataKey="start_minute"
              type="number"
              domain={[0, 1440 - STEP_MINUTES]}
              ticks={HOUR_TICKS}
              tickFormatter={(m: number) => formatMinute(m, timeFormat)}
              {...AXIS_PROPS}
            />
            <YAxis {...AXIS_PROPS} width={40} domain={[0, top]} tickCount={5} />
            <Tooltip content={renderTooltip} cursor={{ stroke: 'var(--ps-muted)', strokeDasharray: '3 3' }} />
            <Area type="stepAfter" dataKey="fixed_kw" stackId="kw" stroke={SERIES.primary} strokeWidth={2} fill={SERIES.primary} fillOpacity={0.35} {...chartMotion()} />
            <Area type="stepAfter" dataKey="flexible_kw" stackId="kw" stroke={SERIES.secondary} strokeWidth={2} fill={SERIES.secondary} fillOpacity={0.35} {...chartMotion()} />
            {limitKw !== null && <ReferenceLine y={limitKw} stroke={LIMIT_COLOR} strokeDasharray="6 4" strokeWidth={2} />}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
