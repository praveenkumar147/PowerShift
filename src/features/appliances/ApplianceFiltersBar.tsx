import { Search } from 'lucide-react';
import { Select, TextInput } from '@/components/ui/inputs';
import { CATEGORIES, CATEGORY_LABELS, type ApplianceFilters } from '@/features/appliances/types';

interface ApplianceFiltersBarProps {
  filters: ApplianceFilters;
  onChange: (filters: ApplianceFilters) => void;
}

export function ApplianceFiltersBar({ filters, onChange }: ApplianceFiltersBarProps) {
  return (
    <div className="mb-4 grid grid-cols-[minmax(0,1fr)_11rem_9rem] gap-3">
      <div className="relative">
        <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
        <TextInput
          type="search"
          aria-label="Search appliances"
          placeholder="Search by name"
          className="pl-9"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
        />
      </div>
      <Select
        aria-label="Filter by category"
        value={filters.category}
        onChange={(e) => onChange({ ...filters, category: e.target.value as ApplianceFilters['category'] })}
      >
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>
            {CATEGORY_LABELS[c]}
          </option>
        ))}
      </Select>
      <Select
        aria-label="Filter by type"
        value={filters.mode}
        onChange={(e) => onChange({ ...filters, mode: e.target.value as ApplianceFilters['mode'] })}
      >
        <option value="">All types</option>
        <option value="fixed">Fixed</option>
        <option value="flexible">Flexible</option>
      </Select>
    </div>
  );
}
