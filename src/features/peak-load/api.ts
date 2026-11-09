import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { PeakLoadAnalysis } from '@/features/peak-load/types';
import { energyQueryKey } from '@/features/tariffs/api';

/** `weekday` null = let the backend pick the day with the highest peak. */
export function usePeakLoad(weekday: number | null) {
  const client = useApiClient();
  return useQuery({
    // Under the energy key, so appliance and household changes refresh it too.
    queryKey: [...energyQueryKey, 'peak-load', weekday],
    queryFn: () => client.get<PeakLoadAnalysis>(`/api/peak-load/analysis${weekday === null ? '' : `?weekday=${weekday}`}`),
    placeholderData: keepPreviousData,
  });
}
