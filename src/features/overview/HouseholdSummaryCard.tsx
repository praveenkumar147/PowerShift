import { Home } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { LinkButton } from '@/components/ui/LinkButton';
import { Spinner } from '@/components/ui/Spinner';
import { useAppliances } from '@/features/appliances/api';
import { useHousehold } from '@/features/household/api';
import { formatKw } from '@/lib/format';

const ALL = { search: '', category: '', mode: '' } as const;

export function HouseholdSummaryCard() {
  const household = useHousehold();
  const appliances = useAppliances(ALL);

  if (household.isPending || appliances.isPending) return <Spinner label="Loading household" />;
  if (household.isError || appliances.isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        {(household.error ?? appliances.error)?.message}
      </p>
    );
  }

  if (household.data === null) {
    return (
      <EmptyState
        icon={Home}
        title="Set up your household"
        message="Start with your household's load limit and currency, then add your appliances."
        action={<LinkButton to="/settings">Set up household</LinkButton>}
      />
    );
  }

  const list = appliances.data;
  const flexibleCount = list.filter((a) => a.mode === 'flexible').length;

  return (
    <Card title={household.data.name} description={household.data.location_label ?? undefined}>
      <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
        <Stat label="Occupants" value={String(household.data.occupants)} />
        <Stat label="Load limit" value={formatKw(household.data.max_load_kw)} />
        <Stat label="Fixed appliances" value={String(list.length - flexibleCount)} />
        <Stat label="Flexible appliances" value={String(flexibleCount)} />
      </dl>
      <div className="mt-6 flex items-center justify-between gap-4 border-t border-border pt-4">
        <p className="text-sm text-muted">
          {list.length === 0
            ? 'Add appliances to start estimating consumption.'
            : 'Consumption and cost analysis arrive with tariffs in Stage 3.'}
        </p>
        {list.length === 0 && <LinkButton to="/appliances">Add appliances</LinkButton>}
      </div>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
