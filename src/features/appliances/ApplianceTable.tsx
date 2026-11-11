import { AlertTriangle, Pencil, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { describeDays, describeUsage } from '@/features/appliances/describe';
import { CATEGORY_LABELS, type Appliance } from '@/features/appliances/types';
import { formatKwh, formatWatts } from '@/lib/format';
import type { TimeFormat } from '@/lib/time';

interface ApplianceTableProps {
  appliances: Appliance[];
  timeFormat: TimeFormat;
  onEdit: (appliance: Appliance) => void;
  onDelete: (appliance: Appliance) => void;
}

export function ApplianceTable({ appliances, timeFormat, onEdit, onDelete }: ApplianceTableProps) {
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface shadow-card">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-muted">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">Appliance</th>
            <th scope="col" className="px-4 py-3 font-medium">Type</th>
            <th scope="col" className="px-4 py-3 font-medium">Power</th>
            <th scope="col" className="px-4 py-3 font-medium">Usage</th>
            <th scope="col" className="px-4 py-3 text-right font-medium">Est. energy / day</th>
            <th scope="col" className="px-4 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {appliances.map((appliance) => (
            <tr key={appliance.id} className="align-top">
              <td className="px-4 py-3">
                <div className="flex items-center gap-1.5 font-medium">
                  {appliance.name}
                  {appliance.warnings.length > 0 && (
                    <AlertTriangle aria-label={appliance.warnings.join(' ')} className="size-4 text-warning" />
                  )}
                </div>
                <div className="text-xs text-muted">{CATEGORY_LABELS[appliance.category]}</div>
                {appliance.warnings.map((warning) => (
                  <p key={warning} className="mt-1 max-w-xs text-xs text-warning">
                    {warning}
                  </p>
                ))}
              </td>
              <td className="px-4 py-3">
                <Badge tone={appliance.mode === 'flexible' ? 'accent' : 'neutral'}>
                  {appliance.mode === 'flexible' ? 'Flexible' : 'Fixed'}
                </Badge>
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                <div>
                  {formatWatts(appliance.rated_power_w)}
                  {appliance.quantity > 1 && <span className="text-muted"> × {appliance.quantity}</span>}
                </div>
                <div className="text-xs text-muted">
                  avg {formatWatts(appliance.estimates.average_power_kw * 1000)} at {Math.round(appliance.duty_cycle * 100)}% duty
                </div>
              </td>
              <td className="px-4 py-3">
                <div>{describeUsage(appliance, timeFormat)}</div>
                <div className="text-xs text-muted">{describeDays(appliance.operating_days)}</div>
              </td>
              <td className="px-4 py-3 text-right whitespace-nowrap tabular-nums">
                {formatKwh(appliance.estimates.energy_per_operating_day_kwh)}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-1">
                  <button
                    type="button"
                    aria-label={`Edit ${appliance.name}`}
                    onClick={() => onEdit(appliance)}
                    className="rounded p-1.5 text-muted hover:bg-surface-raised hover:text-fg"
                  >
                    <Pencil aria-hidden className="size-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${appliance.name}`}
                    onClick={() => onDelete(appliance)}
                    className="rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                  >
                    <Trash2 aria-hidden className="size-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
