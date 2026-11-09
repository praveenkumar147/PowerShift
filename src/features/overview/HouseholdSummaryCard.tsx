import { Card } from '@/components/ui/Card';
import { LinkButton } from '@/components/ui/LinkButton';
import type { Appliance } from '@/features/appliances/types';
import type { Household } from '@/features/household/api';
import { formatKw } from '@/lib/format';

interface HouseholdSummaryCardProps {
  household: Household | null;
  appliances: Appliance[];
}

export function HouseholdSummaryCard({ household, appliances }: HouseholdSummaryCardProps) {
  const flexibleCount = appliances.filter((a) => a.mode === 'flexible').length;
  return (
    <Card title={household?.name ?? 'Household'} description={household?.location_label ?? undefined}>
      <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
        <Stat label="Occupants" value={household ? String(household.occupants) : '—'} />
        <Stat label="Load limit" value={household ? formatKw(household.max_load_kw) : '—'} />
        <Stat label="Fixed appliances" value={String(appliances.length - flexibleCount)} />
        <Stat label="Flexible appliances" value={String(flexibleCount)} />
      </dl>
      {(household === null || appliances.length === 0) && (
        <div className="mt-6 flex items-center justify-between gap-4 border-t border-border pt-4">
          <p className="text-sm text-muted">
            {household === null ? 'Set your load limit and currency to complete the profile.' : 'Add appliances to start estimating consumption.'}
          </p>
          <LinkButton to={household === null ? '/settings' : '/appliances'}>{household === null ? 'Set up household' : 'Add appliances'}</LinkButton>
        </div>
      )}
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
