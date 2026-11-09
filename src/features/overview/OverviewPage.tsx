import { PageHeader } from '@/components/ui/PageHeader';
import { HouseholdSummaryCard } from '@/features/overview/HouseholdSummaryCard';
import { SystemStatusCard } from '@/features/overview/SystemStatusCard';

export function OverviewPage() {
  return (
    <>
      <PageHeader title="Overview" description="Household energy at a glance." />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <HouseholdSummaryCard />
        </div>
        <SystemStatusCard />
      </div>
    </>
  );
}
