interface StatTileProps {
  label: string;
  value: string;
  detail?: string | undefined;
}

/** A single headline number. Used where a chart would add nothing. */
export function StatTile({ label, value, detail }: StatTileProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-2 truncate text-2xl font-semibold tabular-nums" title={value}>
        {value}
      </p>
      {detail && <p className="mt-1 truncate text-xs text-muted" title={detail}>{detail}</p>}
    </div>
  );
}
