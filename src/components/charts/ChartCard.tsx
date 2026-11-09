import type { ReactNode } from 'react';
import { Card } from '@/components/ui/Card';

interface ChartCardProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  /** Accessible table of the same numbers, shown on demand. */
  table?: ReactNode;
  className?: string;
}

/** A titled chart with an optional "Show data table" view (charts must never be the only way to read the data). */
export function ChartCard({ title, description, actions, children, table, className }: ChartCardProps) {
  return (
    <Card className={className}>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
        </div>
        {actions}
      </header>
      {children}
      {table && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer text-muted hover:text-fg">Show data table</summary>
          <div className="mt-3 max-h-72 overflow-auto">{table}</div>
        </details>
      )}
    </Card>
  );
}

interface DataTableProps {
  caption: string;
  columns: string[];
  rows: Array<Array<string | number>>;
}

export function DataTable({ caption, columns, rows }: DataTableProps) {
  return (
    <table className="w-full text-left text-sm tabular-nums">
      <caption className="sr-only">{caption}</caption>
      <thead className="text-xs uppercase tracking-wide text-muted">
        <tr>
          {columns.map((column, i) => (
            <th key={column} scope="col" className={i === 0 ? 'py-1.5 pr-4 font-medium' : 'py-1.5 pr-4 text-right font-medium'}>
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map((row, r) => (
          <tr key={r}>
            {row.map((cell, i) => (
              <td key={i} className={i === 0 ? 'py-1.5 pr-4' : 'py-1.5 pr-4 text-right'}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
