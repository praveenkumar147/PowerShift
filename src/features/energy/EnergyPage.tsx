import { BarChart3, Info } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { fieldErrorsOf } from '@/api/client';
import { ChartCard, DataTable } from '@/components/charts/ChartCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { LinkButton } from '@/components/ui/LinkButton';
import { PageHeader } from '@/components/ui/PageHeader';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Spinner } from '@/components/ui/Spinner';
import { StatTile } from '@/components/ui/StatTile';
import { CATEGORY_LABELS } from '@/features/appliances/types';
import { useEnergyReport, useMonthlyProjection } from '@/features/energy/api';
import { BillEstimateCard } from '@/features/energy/BillEstimateCard';
import { BreakdownChart, type BreakdownItem, type BreakdownMetric } from '@/features/energy/charts/BreakdownChart';
import { DailyEnergyChart, DailyEnergyTable } from '@/features/energy/charts/DailyEnergyChart';
import { MonthlyProjectionChart, MonthlyProjectionTable } from '@/features/energy/charts/MonthlyProjectionChart';
import { EnergyFiltersBar } from '@/features/energy/EnergyFiltersBar';
import { HourlyProfileSection } from '@/features/energy/HourlyProfileSection';
import type { EnergyFilters, EnergyReport } from '@/features/energy/types';
import { useHousehold } from '@/features/household/api';
import { monthRange, parseIsoDate } from '@/lib/dates';
import { formatKwh, formatMoney, formatShare } from '@/lib/format';

function currentMonthFilters(): EnergyFilters {
  const now = new Date();
  return { ...monthRange(now.getFullYear(), now.getMonth() + 1), category: '' };
}

export function EnergyPage() {
  const [filters, setFilters] = useState<EnergyFilters>(currentMonthFilters);
  const deferred = useDeferredValue(filters);
  const report = useEnergyReport(deferred);
  const currency = useHousehold().data?.currency_code ?? null;
  const rangeError = fieldErrorsOf(report.error).end;

  return (
    <>
      <PageHeader title="Energy Analysis" description="Estimated consumption and energy charges from your appliance settings." />
      <EnergyFiltersBar filters={filters} onChange={setFilters} error={rangeError} />

      {report.isPending && <Spinner label="Calculating" />}
      {report.isError && !rangeError && (
        <p role="alert" className="text-sm text-danger">
          {report.error.message}
        </p>
      )}
      {report.data && report.data.appliances.length === 0 && !filters.category && (
        <EmptyState
          icon={BarChart3}
          title="Nothing to analyse yet"
          message="Add appliances to see estimated consumption."
          action={<LinkButton to="/appliances">Add appliances</LinkButton>}
        />
      )}
      {report.data && (report.data.appliances.length > 0 || filters.category) && (
        <EnergyReportView report={report.data} filters={deferred} currency={currency} />
      )}
    </>
  );
}

function EnergyReportView({ report, filters, currency }: { report: EnergyReport; filters: EnergyFilters; currency: string | null }) {
  const [metric, setMetric] = useState<BreakdownMetric>('kwh');
  const year = parseIsoDate(filters.start).getFullYear();
  const projection = useMonthlyProjection(year, filters.category);
  const priced = report.energy_charge !== null;
  const top = report.appliances[0];

  const applianceItems: BreakdownItem[] = report.appliances.map((a) => ({ key: String(a.appliance_id), label: a.name, kwh: a.kwh, share: a.share, energy_charge: a.energy_charge }));
  const categoryItems: BreakdownItem[] = report.categories.map((c) => ({ key: c.category, label: CATEGORY_LABELS[c.category], kwh: c.kwh, share: c.share, energy_charge: c.energy_charge }));
  const sortedItems = metric === 'cost' ? [...applianceItems].sort((a, b) => (b.energy_charge ?? 0) - (a.energy_charge ?? 0)) : applianceItems;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Estimated energy" value={formatKwh(report.total_kwh)} detail={`${report.days} days`} />
        <StatTile label="Average per day" value={formatKwh(report.average_daily_kwh)} />
        <StatTile
          label="Energy charge"
          value={priced ? formatMoney(report.energy_charge ?? 0, currency) : 'No tariff'}
          detail={priced ? 'Excludes fixed charges and taxes' : 'Add a tariff to see costs'}
        />
        <StatTile label="Largest consumer" value={top ? top.name : '—'} detail={top ? `${formatShare(top.share)} of energy` : undefined} />
      </div>

      <ChartCard title="Daily consumption" description="Estimated energy for each day in the selected range." table={<DailyEnergyTable daily={report.daily} currency={currency} />}>
        <DailyEnergyChart daily={report.daily} currency={currency} />
      </ChartCard>

      <div className="grid gap-6 lg:grid-cols-5">
        <ChartCard
          className="lg:col-span-3"
          title="By appliance"
          description="Which appliances use the most."
          actions={
            priced && (
              <div className="w-48">
                <SegmentedControl
                  label="Measure"
                  size="sm"
                  options={[
                    { value: 'kwh', label: 'Energy' },
                    { value: 'cost', label: 'Cost' },
                  ]}
                  value={metric}
                  onChange={setMetric}
                />
              </div>
            )
          }
          table={
            <DataTable
              caption="Energy by appliance"
              columns={['Appliance', 'Energy', 'Share', ...(priced ? ['Energy charge'] : [])]}
              rows={report.appliances.map((a) => [
                a.name,
                formatKwh(a.kwh),
                formatShare(a.share),
                ...(priced ? [formatMoney(a.energy_charge ?? 0, currency)] : []),
              ])}
            />
          }
        >
          <BreakdownChart items={sortedItems} metric={metric} currency={currency} label={`Bar chart of ${metric === 'kwh' ? 'energy' : 'energy charge'} by appliance`} />
        </ChartCard>
        <ChartCard
          className="lg:col-span-2"
          title="By category"
          table={
            <DataTable
              caption="Energy by category"
              columns={['Category', 'Energy', 'Share']}
              rows={report.categories.map((c) => [CATEGORY_LABELS[c.category], formatKwh(c.kwh), formatShare(c.share)])}
            />
          }
        >
          <BreakdownChart items={categoryItems} metric="kwh" currency={currency} label="Bar chart of energy by category" nameWidth={104} />
        </ChartCard>
      </div>

      <HourlyProfileSection currency={currency} category={filters.category} />

      <div className="grid gap-6 lg:grid-cols-5">
        <ChartCard
          className="lg:col-span-3"
          title={`Monthly projection ${year}`}
          description="Energy per month; months differ by length and weekday mix."
          table={projection.data && <MonthlyProjectionTable months={projection.data.months} currency={currency} />}
        >
          {projection.isPending && <Spinner label="Loading projection" />}
          {projection.data && <MonthlyProjectionChart months={projection.data.months} currency={currency} />}
        </ChartCard>
        <div className="lg:col-span-2">
          {/* key: picking a new range resets the card to that range's first month */}
          <BillEstimateCard key={filters.start} year={year} initialMonth={parseIsoDate(filters.start).getMonth() + 1} currency={currency} />
        </div>
      </div>

      <section aria-label="How these figures are calculated" className="rounded-xl border border-border bg-surface-raised p-4 text-sm text-muted">
        <p className="mb-2 flex items-center gap-2 font-medium text-fg">
          <Info aria-hidden className="size-4" /> How these figures are calculated
        </p>
        <ul className="list-disc space-y-1 pl-5">
          {report.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
