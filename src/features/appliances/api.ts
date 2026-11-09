import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { Appliance, ApplianceFilters, ApplianceInput } from '@/features/appliances/types';
import { energyQueryKey } from '@/features/tariffs/api';

export const appliancesQueryKey = ['appliances'] as const;

function toQueryString(filters: ApplianceFilters): string {
  const params = new URLSearchParams();
  if (filters.search.trim()) params.set('q', filters.search.trim());
  if (filters.category) params.set('category', filters.category);
  if (filters.mode) params.set('mode', filters.mode);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export function useAppliances(filters: ApplianceFilters) {
  const client = useApiClient();
  return useQuery({
    queryKey: [...appliancesQueryKey, filters],
    queryFn: () => client.get<Appliance[]>(`/api/appliances${toQueryString(filters)}`),
    // Keep showing the previous list while a new search loads (no flicker).
    placeholderData: keepPreviousData,
  });
}

/** Appliance changes affect the list and every energy figure. */
function useInvalidateApplianceData() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: appliancesQueryKey }),
      queryClient.invalidateQueries({ queryKey: energyQueryKey }),
    ]);
}

/** Creates when `id` is null, otherwise replaces the appliance. */
export function useSaveAppliance(id: number | null) {
  const client = useApiClient();
  const invalidate = useInvalidateApplianceData();
  return useMutation({
    mutationFn: (input: ApplianceInput) =>
      id === null
        ? client.send<Appliance>('POST', '/api/appliances', input)
        : client.send<Appliance>('PUT', `/api/appliances/${id}`, input),
    onSuccess: invalidate,
  });
}

export function useDeleteAppliance() {
  const client = useApiClient();
  const invalidate = useInvalidateApplianceData();
  return useMutation({
    mutationFn: (id: number) => client.send<undefined>('DELETE', `/api/appliances/${id}`),
    onSuccess: invalidate,
  });
}
