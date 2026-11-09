import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { TimeFormat } from '@/lib/time';

/** Mirrors backend/powershift/schemas/household.py */
export interface Household {
  name: string;
  occupants: number;
  location_label: string | null;
  max_load_kw: number;
  currency_code: string;
  time_format: TimeFormat;
}

export const householdQueryKey = ['household'] as const;

/** `data` is null until the household has been set up. */
export function useHousehold() {
  const client = useApiClient();
  return useQuery({
    queryKey: householdQueryKey,
    queryFn: () => client.get<Household | null>('/api/household'),
  });
}

export function useSaveHousehold() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (household: Household) => client.send<Household>('PUT', '/api/household', household),
    onSuccess: (saved) => {
      queryClient.setQueryData(householdQueryKey, saved);
      // Appliance warnings, peak load and money formatting depend on the household.
      void queryClient.invalidateQueries({ queryKey: ['appliances'] });
      void queryClient.invalidateQueries({ queryKey: ['energy'] });
    },
  });
}

/** The user's preferred time format, defaulting to 24-hour before setup. */
export function useTimeFormat(): TimeFormat {
  return useHousehold().data?.time_format ?? '24h';
}
