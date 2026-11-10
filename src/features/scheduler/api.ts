import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { OptimizationRequest, OptimizationRun, OptimizationSummary } from '@/features/scheduler/types';

const historyKey = ['optimization', 'history'] as const;
const runKey = (id: number) => ['optimization', 'run', id] as const;

export function useOptimizationHistory() {
  const client = useApiClient();
  return useQuery({ queryKey: historyKey, queryFn: () => client.get<OptimizationSummary[]>('/api/optimization/history') });
}

/** A stored run never changes, so it is cached indefinitely. */
export function useOptimizationRun(id: number | null) {
  const client = useApiClient();
  return useQuery({
    queryKey: runKey(id ?? 0),
    queryFn: () => client.get<OptimizationRun>(`/api/optimization/${id}`),
    enabled: id !== null,
    staleTime: Infinity,
  });
}

export function useRunOptimization() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: OptimizationRequest) => client.send<OptimizationRun>('POST', '/api/optimization/run', request),
    onSuccess: (run) => {
      queryClient.setQueryData(runKey(run.id), run);
      return queryClient.invalidateQueries({ queryKey: historyKey });
    },
  });
}
