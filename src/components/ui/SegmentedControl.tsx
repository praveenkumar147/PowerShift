import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  icon?: LucideIcon;
}

interface SegmentedControlProps<T extends string> {
  label: string;
  options: ReadonlyArray<SegmentOption<T>>;
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
}

/** A row of mutually exclusive buttons (accessible as a radio group). */
export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
  size = 'md',
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="grid gap-1 rounded-control border border-border bg-surface-raised p-1"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {options.map(({ value: optionValue, label: optionLabel, icon: Icon }) => {
        const selected = optionValue === value;
        return (
          <button
            key={optionValue}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(optionValue)}
            className={cn(
              'flex items-center justify-center gap-1.5 rounded-lg transition-colors duration-150',
              size === 'sm' ? 'px-2 py-1.5 text-xs' : 'px-3 py-2 text-sm',
              selected ? 'bg-accent font-medium text-accent-fg' : 'text-muted hover:text-fg',
            )}
          >
            {Icon && <Icon aria-hidden className={size === 'sm' ? 'size-3.5' : 'size-4'} />}
            {optionLabel}
          </button>
        );
      })}
    </div>
  );
}
