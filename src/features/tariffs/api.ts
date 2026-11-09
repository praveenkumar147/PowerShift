import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { Tariff, TariffInput } from '@/features/tariffs/types';

export const tariffsQueryKey = ['tariffs'] as const;
/** Every energy/cost figure depends on the active tariff and the appliances. */
export const energyQueryKey = ['energy'] as const;

export function useTariffs() {
  const client = useApiClient();
  return useQuery({ queryKey: tariffsQueryKey, queryFn: () => client.get<Tariff[]>('/api/tariffs') });
}

function useInvalidateTariffData() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: tariffsQueryKey }),
      queryClient.invalidateQueries({ queryKey: energyQueryKey }),
    ]);
}

export function useSaveTariff(id: number | null) {
  const client = useApiClient();
  const invalidate = useInvalidateTariffData();
  return useMutation({
    mutationFn: (input: TariffInput) =>
      id === null ? client.send<Tariff>('POST', '/api/tariffs', input) : client.send<Tariff>('PUT', `/api/tariffs/${id}`, input),
    onSuccess: invalidate,
  });
}

export function useActivateTariff() {
  const client = useApiClient();
  const invalidate = useInvalidateTariffData();
  return useMutation({
    mutationFn: (id: number) => client.send<Tariff>('POST', `/api/tariffs/${id}/activate`),
    onSuccess: invalidate,
  });
}

export function useDeleteTariff() {
  const client = useApiClient();
  const invalidate = useInvalidateTariffData();
  return useMutation({
    mutationFn: (id: number) => client.send<undefined>('DELETE', `/api/tariffs/${id}`),
    onSuccess: invalidate,
  });
}
