import { StatTile } from '@/components/ui/StatTile';
import { useBillEstimate, useEnergyReport } from '@/features/energy/api';
import { monthLong, monthRange } from '@/lib/dates';
import { formatKwh, formatMoney, formatShare } from '@/lib/format';

/** Headline numbers for the current calendar month. */
export function MonthSummary({ currency }: { currency: string | null }) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const report = useEnergyReport({ ...monthRange(year, month), category: '' });
  const bill = useBillEstimate(year, month);

  if (!report.data) return null;
  const flexibleKwh = report.data.appliances.filter((a) => a.mode === 'flexible').reduce((sum, a) => sum + a.kwh, 0);
  const flexibleShare = report.data.total_kwh ? flexibleKwh / report.data.total_kwh : 0;
  const monthName = monthLong(month);

  return (
    <section aria-label={`${monthName} estimates`} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <StatTile label={`Energy in ${monthName}`} value={formatKwh(report.data.total_kwh)} detail={`${report.data.days} days, estimated`} />
      <StatTile
        label="Estimated bill"
        value={bill.data?.total != null ? formatMoney(bill.data.total, currency) : 'No tariff'}
        detail={bill.data?.tariff ? bill.data.tariff.name : 'Add a tariff to see costs'}
      />
      <StatTile label="Average per day" value={formatKwh(report.data.average_daily_kwh)} />
      <StatTile label="Flexible share" value={formatShare(flexibleShare)} detail="Energy the scheduler could shift" />
    </section>
  );
}
