import { Card } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { Spinner } from '@/components/ui/Spinner';
import { useHousehold } from '@/features/household/api';
import { HouseholdForm } from '@/features/household/HouseholdForm';

export function SettingsPage() {
  const household = useHousehold();

  return (
    <>
      <PageHeader title="Settings" description="Household profile and application preferences." />
      <Card title="Household profile" description="Basic details used across calculations.">
        {household.isPending && <Spinner label="Loading household" />}
        {household.isError && (
          <p role="alert" className="text-sm text-danger">
            {household.error.message}
          </p>
        )}
        {household.isSuccess && <HouseholdForm household={household.data} />}
      </Card>
      <p className="mt-6 text-sm text-muted">Backups, data export and reset are added in Stage 7.</p>
    </>
  );
}
