import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { ApplianceCategory } from '@/features/appliances/types';
import type { BillEstimate, EnergyFilters, EnergyReport, HourlyProfile, MonthlyProjection } from '@/features/energy/types';
import { energyQueryKey } from '@/features/tariffs/api';

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  }
  return search.toString();
}

export function useEnergyReport(filters: EnergyFilters, enabled = true) {
  const client = useApiClient();
  return useQuery({
    queryKey: [...energyQueryKey, 'report', filters],
    queryFn: () => client.get<EnergyReport>(`/api/energy/report?${query({ ...filters })}`),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useHourlyProfile(weekday: number | null, category: ApplianceCategory | '' = '') {
  const client = useApiClient();
  return useQuery({
    queryKey: [...energyQueryKey, 'hourly', weekday, category],
    queryFn: () => client.get<HourlyProfile>(`/api/energy/hourly-profile?${query({ weekday, category })}`),
    placeholderData: keepPreviousData,
  });
}

export function useMonthlyProjection(year: number, category: ApplianceCategory | '' = '') {
  const client = useApiClient();
  return useQuery({
    queryKey: [...energyQueryKey, 'monthly', year, category],
    queryFn: () => client.get<MonthlyProjection>(`/api/energy/monthly?${query({ year, category })}`),
    placeholderData: keepPreviousData,
  });
}

export function useBillEstimate(year: number, month: number) {
  const client = useApiClient();
  return useQuery({
    queryKey: [...energyQueryKey, 'bill', year, month],
    queryFn: () => client.get<BillEstimate>(`/api/energy/bill?${query({ year, month })}`),
    placeholderData: keepPreviousData,
  });
}
