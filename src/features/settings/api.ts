import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { About, BackupInfo, BackupSummary, ResetResult, RestoreResult, RestoreSource } from '@/features/settings/types';
import { saveFile } from '@/lib/download';

const aboutKey = ['settings', 'about'] as const;
const backupsKey = ['settings', 'backups'] as const;

export function useAbout() {
  const client = useApiClient();
  return useQuery({ queryKey: aboutKey, queryFn: () => client.get<About>('/api/settings/about') });
}

export function useBackups() {
  const client = useApiClient();
  return useQuery({ queryKey: backupsKey, queryFn: () => client.get<BackupInfo[]>('/api/settings/backups') });
}

export function useCreateBackup() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.send<BackupInfo>('POST', '/api/settings/backup'),
    onSuccess: () => Promise.all([queryClient.invalidateQueries({ queryKey: backupsKey }), queryClient.invalidateQueries({ queryKey: aboutKey })]),
  });
}

export function useDownloadBackup() {
  const client = useApiClient();
  return useMutation({
    mutationFn: async (name: string) => {
      const file = await client.download(`/api/settings/backups/${encodeURIComponent(name)}`, undefined, name);
      saveFile(file.blob, file.filename);
      return file.filename;
    },
  });
}

/**
 * Validates a backup without changing anything, so the user can see what a restore
 * would replace their data with. Never retried: a rejection is a final answer.
 */
export function useCheckRestore(source: RestoreSource) {
  const client = useApiClient();
  return useQuery({
    queryKey: ['settings', 'restore-check', source.kind === 'stored' ? source.name : source.id],
    queryFn: () =>
      source.kind === 'stored'
        ? client.get<BackupSummary>(`/api/settings/backups/${encodeURIComponent(source.name)}/check`)
        : client.upload<BackupSummary>('/api/settings/restore/check', source.file),
    retry: false,
    gcTime: 0,
  });
}

/** Everything the app shows comes from the database, so after a restore or reset every query is refreshed. */
export function useRestore() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (source: RestoreSource) =>
      source.kind === 'stored'
        ? client.send<RestoreResult>('POST', `/api/settings/backups/${encodeURIComponent(source.name)}/restore`)
        : client.upload<RestoreResult>('/api/settings/restore', source.file),
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useResetData() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.send<ResetResult>('POST', '/api/settings/reset', { confirm: 'RESET' }),
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useExportData() {
  const client = useApiClient();
  return useMutation({
    mutationFn: async () => {
      const file = await client.download('/api/settings/export', undefined, 'powershift-data-export.json');
      saveFile(file.blob, file.filename);
      return file.filename;
    },
  });
}
