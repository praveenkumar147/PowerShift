import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { Scenario, ScenarioInput, SimulationResult } from '@/features/simulation/types';

export const simulationsQueryKey = ['simulations'] as const;

export function useScenarios() {
  const client = useApiClient();
  return useQuery({ queryKey: simulationsQueryKey, queryFn: () => client.get<Scenario[]>('/api/simulations') });
}

/** Creates when `id` is null, otherwise replaces the scenario. */
export function useSaveScenario(id: number | null) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ScenarioInput) =>
      id === null ? client.send<Scenario>('POST', '/api/simulations', input) : client.send<Scenario>('PUT', `/api/simulations/${id}`, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: simulationsQueryKey }),
  });
}

export function useDeleteScenario() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => client.send<undefined>('DELETE', `/api/simulations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: simulationsQueryKey }),
  });
}

export function useRunScenario() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => client.send<SimulationResult>('POST', `/api/simulations/${id}/run`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: simulationsQueryKey }),
  });
}
