import { useState } from 'react';
import { ChartCard } from '@/components/charts/ChartCard';
import { Select } from '@/components/ui/inputs';
import { Spinner } from '@/components/ui/Spinner';
import type { ApplianceCategory } from '@/features/appliances/types';
import { WEEKDAY_SHORT } from '@/features/appliances/types';
import { useHourlyProfile } from '@/features/energy/api';
import { HourlyProfileChart, HourlyProfileTable } from '@/features/energy/charts/HourlyProfileChart';
import { useTimeFormat } from '@/features/household/api';

const AVERAGE = 'avg';

interface HourlyProfileSectionProps {
  currency: string | null;
  category?: ApplianceCategory | '';
  height?: number;
}

export function HourlyProfileSection({ currency, category = '', height }: HourlyProfileSectionProps) {
  const [day, setDay] = useState<string>(AVERAGE);
  const weekday = day === AVERAGE ? null : Number(day);
  const profile = useHourlyProfile(weekday, category);
  const timeFormat = useTimeFormat();

  return (
    <ChartCard
      title="Hourly profile"
      description="Estimated energy in each hour of a typical day. Flexible appliances are shown at their usual start time."
      actions={
        <Select aria-label="Day shown" className="w-44" value={day} onChange={(e) => setDay(e.target.value)}>
          <option value={AVERAGE}>Average day</option>
          {WEEKDAY_SHORT.map((label, i) => (
            <option key={label} value={i}>
              {label}
            </option>
          ))}
        </Select>
      }
      table={profile.data && <HourlyProfileTable hours={profile.data.hours} currency={currency} timeFormat={timeFormat} />}
    >
      {profile.isPending && <Spinner label="Loading hourly profile" />}
      {profile.isError && (
        <p role="alert" className="text-sm text-danger">
          {profile.error.message}
        </p>
      )}
      {profile.data && <HourlyProfileChart hours={profile.data.hours} currency={currency} timeFormat={timeFormat} {...(height ? { height } : {})} />}
    </ChartCard>
  );
}
