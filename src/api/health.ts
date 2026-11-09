import { useQuery } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';

/** Mirrors backend/powershift/schemas/health.py */
export interface HealthResponse {
  status: 'ok';
  version: string;
  schema_revision: string | null;
  database_path: string;
}

export const healthQueryKey = ['health'] as const;

export function useHealth() {
  const client = useApiClient();
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: () => client.get<HealthResponse>('/api/health'),
  });
}
