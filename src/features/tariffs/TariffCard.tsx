import { CheckCircle2, Pencil, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { CHARGE_KIND_LABELS, DAY_TYPE_LABELS, TARIFF_TYPE_LABELS, type Charge, type Tariff } from '@/features/tariffs/types';
import { formatMoney, formatRate } from '@/lib/format';
import { formatWindow, type TimeFormat } from '@/lib/time';

interface TariffCardProps {
  tariff: Tariff;
  currency: string | null;
  timeFormat: TimeFormat;
  onEdit: () => void;
  onDelete: () => void;
  onActivate: () => void;
  activating: boolean;
}

function describeCharge(charge: Charge, currency: string | null): string {
  if (charge.kind === 'percentage') return `${charge.amount}%`;
  if (charge.kind === 'per_kwh') return formatRate(charge.amount, currency);
  return `${formatMoney(charge.amount, currency)}/month`;
}

export function TariffCard({ tariff, currency, timeFormat, onEdit, onDelete, onActivate, activating }: TariffCardProps) {
  return (
    <article className="rounded-xl border border-border bg-surface p-6 shadow-sm" aria-label={tariff.name}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold">{tariff.name}</h2>
            {tariff.is_active && (
              <Badge tone="accent">
                <CheckCircle2 aria-hidden className="mr-1 size-3" /> Active
              </Badge>
            )}
          </div>
          <p className="mt-0.5 text-sm text-muted">
            {TARIFF_TYPE_LABELS[tariff.tariff_type]} · effective from {tariff.effective_date}
          </p>
        </div>
        <div className="flex gap-1">
          {!tariff.is_active && (
            <Button variant="secondary" onClick={onActivate} disabled={activating}>
              Use this tariff
            </Button>
          )}
          <Button variant="ghost" aria-label={`Edit ${tariff.name}`} onClick={onEdit}>
            <Pencil aria-hidden className="size-4" />
          </Button>
          <Button variant="ghost" aria-label={`Delete ${tariff.name}`} onClick={onDelete}>
            <Trash2 aria-hidden className="size-4" />
          </Button>
        </div>
      </header>

      <dl className="mt-4 grid gap-6 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Energy price</dt>
          <dd className="mt-1.5">
            {tariff.tariff_type === 'flat' && tariff.flat_rate_per_kwh !== null && formatRate(tariff.flat_rate_per_kwh, currency)}
            {tariff.tariff_type === 'tou' && (
              <ul className="space-y-1">
                {tariff.tou_periods.map((p, i) => (
                  <li key={i} className="flex justify-between gap-4 tabular-nums">
                    <span>
                      {formatWindow(p.start_minute, p.end_minute, timeFormat)}
                      {p.day_type !== 'all' && <span className="text-muted"> · {DAY_TYPE_LABELS[p.day_type]}</span>}
                    </span>
                    <span>{formatRate(p.rate_per_kwh, currency)}</span>
                  </li>
                ))}
              </ul>
            )}
            {tariff.tariff_type === 'slab' && (
              <ul className="space-y-1">
                {tariff.slabs.map((s, i) => {
                  const from = i === 0 ? 0 : (tariff.slabs[i - 1]?.up_to_kwh ?? 0);
                  return (
                    <li key={i} className="flex justify-between gap-4 tabular-nums">
                      <span>{s.up_to_kwh === null ? `Above ${from} kWh` : `${from}–${s.up_to_kwh} kWh`}</span>
                      <span>{formatRate(s.rate_per_kwh, currency)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Additional charges</dt>
          <dd className="mt-1.5">
            {tariff.charges.length === 0 ? (
              <span className="text-muted">None</span>
            ) : (
              <ul className="space-y-1">
                {tariff.charges.map((c, i) => (
                  <li key={i} className="flex justify-between gap-4 tabular-nums">
                    <span>
                      {c.label} <span className="text-muted">· {CHARGE_KIND_LABELS[c.kind]}</span>
                    </span>
                    <span>{describeCharge(c, currency)}</span>
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
      </dl>
    </article>
  );
}
