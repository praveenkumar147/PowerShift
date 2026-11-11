import { Home } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { LinkButton } from '@/components/ui/LinkButton';
import { PageHeader } from '@/components/ui/PageHeader';
import { Spinner } from '@/components/ui/Spinner';
import { useAppliances } from '@/features/appliances/api';
import { useLoadSampleData } from '@/features/demo/api';
import { HourlyProfileSection } from '@/features/energy/HourlyProfileSection';
import { useHousehold } from '@/features/household/api';
import { HouseholdSummaryCard } from '@/features/overview/HouseholdSummaryCard';
import { BackupCard, SchedulerCard, SimulationCard } from '@/features/overview/ActivityCards';
import { MonthSummary } from '@/features/overview/MonthSummary';
import { SystemStatusCard } from '@/features/overview/SystemStatusCard';

const ALL = { search: '', category: '', mode: '' } as const;

export function OverviewPage() {
  const household = useHousehold();
  const appliances = useAppliances(ALL);
  const currency = household.data?.currency_code ?? null;
  const isEmpty = household.data === null && appliances.data?.length === 0;

  return (
    <>
      <PageHeader title="Overview" description="Household energy at a glance. All figures are estimates." />
      {(household.isPending || appliances.isPending) && <Spinner label="Loading" />}
      {(household.isError || appliances.isError) && (
        <p role="alert" className="text-sm text-danger">
          {(household.error ?? appliances.error)?.message}
        </p>
      )}

      {isEmpty && <GettingStarted />}

      {household.isSuccess && appliances.isSuccess && !isEmpty && (
        <div className="space-y-6">
          {appliances.data.length > 0 && <MonthSummary currency={currency} />}
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              {appliances.data.length > 0 && <HourlyProfileSection currency={currency} height={200} />}
              <HouseholdSummaryCard household={household.data} appliances={appliances.data} />
            </div>
            <SystemStatusCard />
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <SchedulerCard currency={currency} />
            <SimulationCard currency={currency} />
            <BackupCard />
          </div>
        </div>
      )}
    </>
  );
}

function GettingStarted() {
  const sample = useLoadSampleData();
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <EmptyState
          icon={Home}
          title="Set up your household"
          message="Start with your load limit and currency, then add appliances and your tariff. Or explore with sample data first: it is clearly labelled and uses invented rates."
          action={
            <div className="flex flex-wrap justify-center gap-3">
              <LinkButton to="/settings">Set up household</LinkButton>
              <Button variant="secondary" onClick={() => sample.mutate()} disabled={sample.isPending}>
                {sample.isPending ? 'Loading…' : 'Load sample data'}
              </Button>
            </div>
          }
        />
        {sample.isError && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {sample.error.message}
          </p>
        )}
      </div>
      <SystemStatusCard />
    </div>
  );
}
