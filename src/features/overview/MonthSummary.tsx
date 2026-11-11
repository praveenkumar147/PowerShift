import { Spinner } from '@/components/ui/Spinner';
import { StatTile } from '@/components/ui/StatTile';
import { useBillEstimate, useEnergyReport } from '@/features/energy/api';
import { usePeakLoad } from '@/features/peak-load/api';
import { useOptimizationHistory } from '@/features/scheduler/api';
import { monthLong, monthRange } from '@/lib/dates';
import { formatKw, formatKwh, formatMoney, formatShare, formatSignedMoney } from '@/lib/format';

/** The four headline numbers for the current calendar month. Each comes from real data; none is invented. */
export function MonthSummary({ currency }: { currency: string | null }) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const report = useEnergyReport({ ...monthRange(year, month), category: '' });
  const bill = useBillEstimate(year, month);
  const peak = usePeakLoad(null);
  const history = useOptimizationHistory();

  if (report.isPending) return <Spinner label="Loading this month's estimates" />;
  if (!report.data) {
    return (
      <p role="alert" className="text-sm text-danger">
        This month's estimates could not be loaded{report.error ? `: ${report.error.message}` : ''}.
      </p>
    );
  }

  const flexibleKwh = report.data.appliances.filter((a) => a.mode === 'flexible').reduce((sum, a) => sum + a.kwh, 0);
  const flexibleShare = report.data.total_kwh ? flexibleKwh / report.data.total_kwh : 0;
  const monthName = monthLong(month);

  // Savings come only from the latest run, and only if its schedule passed every independent check.
  const latest = history.data?.at(0);
  const saving = latest?.schedule_valid && latest.baseline_bill !== null && latest.optimized_bill !== null ? latest.baseline_bill - latest.optimized_bill : null;
  const savingDetail =
    latest === undefined
      ? history.isError
        ? 'Could not load the latest run'
        : 'Run the Smart Scheduler to see this'
      : saving === null
        ? 'The latest run found no valid schedule'
        : saving > 0
          ? `per month, ${latest.status === 'OPTIMAL' ? 'proven optimal' : 'valid, not proven optimal'}`
          : 'The latest run does not reduce the bill';

  return (
    <section aria-label={`${monthName} estimates`} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <StatTile
        index={0}
        label={`Energy in ${monthName}`}
        value={formatKwh(report.data.total_kwh)}
        detail={`${formatKwh(report.data.average_daily_kwh)} a day · ${formatShare(flexibleShare)} flexible`}
      />
      <StatTile
        index={1}
        label="Estimated bill"
        value={bill.data?.total != null ? formatMoney(bill.data.total, currency) : 'No tariff'}
        detail={bill.data?.tariff ? bill.data.tariff.name : 'Add a tariff to see costs'}
      />
      <StatTile
        index={2}
        label="Peak demand"
        value={peak.data ? formatKw(peak.data.peak_kw) : '—'}
        detail={
          peak.data
            ? peak.data.load_limit_kw === null
              ? 'Worst case; no load limit set'
              : `Worst case; limit ${formatKw(peak.data.load_limit_kw)}`
            : peak.isError
              ? 'Could not load the peak'
              : 'Calculating…'
        }
      />
      <StatTile
        index={3}
        floating={saving !== null && saving > 0}
        highlight={saving !== null && saving > 0}
        label="Potential savings"
        value={saving === null ? '—' : saving > 0 ? formatMoney(saving, currency) : formatSignedMoney(-saving, currency)}
        detail={savingDetail}
      />
    </section>
  );
}
