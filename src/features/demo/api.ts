import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';

/** Loads labelled sample data (backend refuses unless the database is empty). */
export function useLoadSampleData() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.send<{ appliances: number; tariffs: number }>('POST', '/api/demo'),
    // Everything changes, so refresh every query.
    onSuccess: () => queryClient.invalidateQueries(),
  });
}
