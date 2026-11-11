/** Mirrors backend/powershift/schemas/data.py */

export type BackupKind = 'manual' | 'pre-migration' | 'pre-restore' | 'pre-reset' | 'other';

export interface BackupInfo {
  name: string;
  kind: BackupKind;
  size_bytes: number;
  created_at: string;
}

/** What a validated backup contains. */
export interface BackupSummary {
  size_bytes: number;
  schema_revision: string;
  /** From an older version; upgraded after the restore. */
  needs_upgrade: boolean;
  household_name: string | null;
  appliances: number;
  tariffs: number;
  scenarios: number;
  optimization_runs: number;
}

export interface RestoreResult {
  restored: BackupSummary;
  /** A copy of the data that was replaced, so the restore can be undone. */
  safety_backup: BackupInfo;
  schema_revision: string;
}

export interface ResetResult {
  removed: Record<string, number>;
  safety_backup: BackupInfo;
}

export interface About {
  app_version: string;
  schema_revision: string | null;
  python_version: string;
  solver: string;
  data_dir: string;
  database_path: string;
  database_size_bytes: number;
  backups_dir: string;
  logs_dir: string;
  counts: Record<string, number>;
}

/** Where a restore comes from: a backup in the backups folder, or a file the user picked. */
export type RestoreSource = { kind: 'stored'; name: string } | { kind: 'file'; file: File; id: number };

export const BACKUP_KIND_LABELS: Record<BackupKind, string> = {
  manual: 'Backup you made',
  'pre-migration': 'Automatic, before an upgrade',
  'pre-restore': 'Automatic, before a restore',
  'pre-reset': 'Automatic, before a reset',
  other: 'Other',
};
