import { Plug } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { SystemStatusCard } from '@/features/overview/SystemStatusCard';

export function OverviewPage() {
  return (
    <>
      <PageHeader title="Overview" description="Household energy at a glance." />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <EmptyState
            icon={Plug}
            title="No household data yet"
            message="Energy figures appear here once appliances and a tariff are configured. Appliance management arrives in Stage 2."
          />
        </div>
        <SystemStatusCard />
      </div>
    </>
  );
}
