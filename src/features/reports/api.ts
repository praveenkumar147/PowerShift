import { useMutation } from '@tanstack/react-query';
import { useApiClient } from '@/api/BackendProvider';
import type { ReportFormat, ReportKind } from '@/features/reports/catalog';
import { saveFile } from '@/lib/download';

export interface ReportParams {
  start?: string;
  end?: string;
  category?: string;
  year?: number;
  month?: number;
  weekday?: number;
  run_id?: number;
  scenario_ids?: number[];
}

export interface ExportRequest {
  type: ReportKind;
  format: ReportFormat;
  params: ReportParams;
}

/** Builds the report on the backend and hands the file to the user. Resolves to the file name. */
export function useExportReport() {
  const client = useApiClient();
  return useMutation({
    mutationFn: async (request: ExportRequest) => {
      const file = await client.download('/api/reports/export', request, `powershift-${request.type}.${request.format}`);
      saveFile(file.blob, file.filename);
      return file.filename;
    },
  });
}
