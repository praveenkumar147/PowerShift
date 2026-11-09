import { Field } from '@/components/ui/Field';
import { Select, TextInput } from '@/components/ui/inputs';
import { CATEGORIES, CATEGORY_LABELS, type ApplianceCategory } from '@/features/appliances/types';
import type { EnergyFilters } from '@/features/energy/types';
import { monthRange, parseIsoDate, yearRange } from '@/lib/dates';

interface EnergyFiltersBarProps {
  filters: EnergyFilters;
  onChange: (filters: EnergyFilters) => void;
  error?: string | undefined;
}

/** Date range and category filters, in one row above the charts. */
export function EnergyFiltersBar({ filters, onChange, error }: EnergyFiltersBarProps) {
  const anchor = parseIsoDate(filters.start);
  const presets = [
    { label: 'This month', range: monthRange(anchor.getFullYear(), anchor.getMonth() + 1) },
    { label: 'Whole year', range: yearRange(anchor.getFullYear()) },
  ];

  return (
    <div className="mb-6 rounded-xl border border-border bg-surface p-4 shadow-sm">
      <div className="grid items-end gap-4 md:grid-cols-[1fr_1fr_1fr_auto]">
        <Field label="From" error={error}>
          {(p) => <TextInput {...p} type="date" value={filters.start} max={filters.end} onChange={(e) => e.target.value && onChange({ ...filters, start: e.target.value })} />}
        </Field>
        <Field label="To">
          {(p) => <TextInput {...p} type="date" value={filters.end} min={filters.start} onChange={(e) => e.target.value && onChange({ ...filters, end: e.target.value })} />}
        </Field>
        <Field label="Category">
          {(p) => (
            <Select {...p} value={filters.category} onChange={(e) => onChange({ ...filters, category: e.target.value as ApplianceCategory | '' })}>
              <option value="">All categories</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="flex gap-2">
          {presets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => onChange({ ...filters, ...preset.range })}
              className="rounded-md border border-border px-3 py-2 text-sm text-muted hover:bg-surface-raised hover:text-fg"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
