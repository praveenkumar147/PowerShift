import { Card } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { Spinner } from '@/components/ui/Spinner';
import { useHousehold } from '@/features/household/api';
import { HouseholdForm } from '@/features/household/HouseholdForm';
import { AboutCard } from '@/features/settings/AboutCard';
import { BackupsCard } from '@/features/settings/BackupsCard';
import { DataCard } from '@/features/settings/DataCard';

export function SettingsPage() {
  const household = useHousehold();

  return (
    <>
      <PageHeader title="Settings" description="Household profile, backups and local data." />
      <div className="space-y-6">
        <Card title="Household profile" description="Basic details used across calculations.">
          {household.isPending && <Spinner label="Loading household" />}
          {household.isError && (
            <p role="alert" className="text-sm text-danger">
              {household.error.message}
            </p>
          )}
          {household.isSuccess && <HouseholdForm household={household.data} />}
        </Card>
        <BackupsCard />
        <DataCard />
        <AboutCard />
      </div>
    </>
  );
}
