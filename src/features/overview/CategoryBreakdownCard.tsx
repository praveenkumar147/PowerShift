import { ChartCard } from '@/components/charts/ChartCard';
import { DataTable } from '@/components/charts/ChartCard';
import { Spinner } from '@/components/ui/Spinner';
import { CATEGORY_LABELS } from '@/features/appliances/types';
import { useEnergyReport } from '@/features/energy/api';
import { BreakdownChart, type BreakdownItem } from '@/features/energy/charts/BreakdownChart';
import { monthLong, monthRange } from '@/lib/dates';
import { formatKwh, formatShare } from '@/lib/format';

/** Where this month's energy goes, by appliance category (the same report as Energy Analysis). */
export function CategoryBreakdownCard({ currency }: { currency: string | null }) {
  const now = new Date();
  const report = useEnergyReport({ ...monthRange(now.getFullYear(), now.getMonth() + 1), category: '' });
  const items: BreakdownItem[] = (report.data?.categories ?? []).map((c) => ({
    key: c.category,
    label: CATEGORY_LABELS[c.category],
    kwh: c.kwh,
    share: c.share,
    energy_charge: c.energy_charge,
  }));

  return (
    <ChartCard
      title="Where your energy goes"
      description={`Estimated energy by appliance category, ${monthLong(now.getMonth() + 1)}.`}
      index={5}
      table={
        items.length > 0 && (
          <DataTable caption="Energy by category" columns={['Category', 'Energy', 'Share']} rows={items.map((i) => [i.label, formatKwh(i.kwh), formatShare(i.share)])} />
        )
      }
    >
      {report.isPending && <Spinner label="Loading the breakdown" />}
      {report.isError && (
        <p role="alert" className="text-sm text-danger">
          {report.error.message}
        </p>
      )}
      {items.length > 0 && <BreakdownChart items={items} metric="kwh" currency={currency} label="Bar chart of energy by category" nameWidth={104} />}
    </ChartCard>
  );
}
