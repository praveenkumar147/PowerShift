import { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Select } from '@/components/ui/inputs';
import { Spinner } from '@/components/ui/Spinner';
import { useBillEstimate } from '@/features/energy/api';
import { monthLong } from '@/lib/dates';
import { formatKwh, formatMoney, formatRate } from '@/lib/format';

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

interface BillEstimateCardProps {
  year: number;
  initialMonth: number;
  currency: string | null;
}

/** Itemised monthly bill for the whole household under the active tariff. */
export function BillEstimateCard({ year, initialMonth, currency }: BillEstimateCardProps) {
  const [month, setMonth] = useState(initialMonth);
  const bill = useBillEstimate(year, month);

  return (
    <Card>
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Bill estimate</h2>
          <p className="mt-0.5 text-sm text-muted">{bill.data?.tariff ? bill.data.tariff.name : 'Whole household, one calendar month'}</p>
        </div>
        <Select aria-label="Bill month" className="w-48 shrink-0" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
          {MONTHS.map((m) => (
            <option key={m} value={m}>
              {monthLong(m)} {year}
            </option>
          ))}
        </Select>
      </header>

      {bill.isPending && <Spinner label="Calculating bill" />}
      {bill.isError && (
        <p role="alert" className="text-sm text-danger">
          {bill.error.message}
        </p>
      )}
      {bill.data && bill.data.total === null && (
        <p className="text-sm text-muted">
          {formatKwh(bill.data.total_kwh)} estimated for {monthLong(month)}. Add a tariff to see the bill.
        </p>
      )}
      {bill.data && bill.data.total !== null && (
        <table className="w-full text-sm tabular-nums">
          <caption className="sr-only">
            Estimated bill for {monthLong(month)} {year}
          </caption>
          <tbody className="divide-y divide-border">
            {bill.data.lines.map((line) => (
              <tr key={line.label}>
                <th scope="row" className="py-2 pr-4 text-left font-normal">
                  {line.label}
                  <span className="block text-xs text-muted">{line.detail}</span>
                </th>
                <td className="py-2 text-right align-top">{formatMoney(line.amount, currency)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-border">
              <th scope="row" className="py-2 pr-4 text-left font-semibold">
                Estimated total
              </th>
              <td className="py-2 text-right text-base font-semibold">{formatMoney(bill.data.total, currency)}</td>
            </tr>
            <tr>
              <td colSpan={2} className="pt-1 text-xs text-muted">
                {formatKwh(bill.data.total_kwh)} over {bill.data.days} days
                {bill.data.effective_rate_per_kwh !== null && ` · effective ${formatRate(bill.data.effective_rate_per_kwh, currency)}`}
              </td>
            </tr>
          </tfoot>
        </table>
      )}
    </Card>
  );
}
