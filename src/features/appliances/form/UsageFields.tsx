import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Checkbox, Select, TextInput } from '@/components/ui/inputs';
import { ALL_DAY_BLOCK, type ApplianceFormValues, type BlockValues, type FieldErrors } from '@/features/appliances/formModel';
import { ALL_DAYS, WEEKDAYS_ONLY, WEEKDAY_SHORT } from '@/features/appliances/types';
import { cn } from '@/lib/cn';

type Update = (changes: Partial<ApplianceFormValues>) => void;

interface SectionProps {
  values: ApplianceFormValues;
  update: Update;
  errors: FieldErrors;
}

const TIME_STEP_SECONDS = 15 * 60;
const MIDNIGHT_HINT = 'An end time earlier than the start runs past midnight. 00:00 as an end means midnight.';

export function WeekdayPicker({ values, update, errors }: SectionProps) {
  const selected = new Set(values.operatingDays);
  const toggle = (day: number) => {
    const next = new Set(selected);
    if (next.has(day)) next.delete(day);
    else next.add(day);
    update({ operatingDays: [...next].sort((a, b) => a - b) });
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span id="operating-days-label" className="text-sm font-medium">
          Operating days
        </span>
        <div className="flex gap-1 text-xs">
          <button type="button" className="rounded px-2 py-1 text-accent-ink hover:bg-accent-soft" onClick={() => update({ operatingDays: [...ALL_DAYS] })}>
            Every day
          </button>
          <button type="button" className="rounded px-2 py-1 text-accent-ink hover:bg-accent-soft" onClick={() => update({ operatingDays: [...WEEKDAYS_ONLY] })}>
            Weekdays
          </button>
        </div>
      </div>
      <div role="group" aria-labelledby="operating-days-label" className="grid grid-cols-7 gap-1.5">
        {WEEKDAY_SHORT.map((label, day) => (
          <button
            key={label}
            type="button"
            aria-pressed={selected.has(day)}
            onClick={() => toggle(day)}
            className={cn(
              'rounded-control border py-2 text-sm transition-colors',
              selected.has(day) ? 'border-accent-ink bg-accent-soft font-medium text-accent-ink' : 'border-border text-muted hover:text-fg',
            )}
          >
            {label}
          </button>
        ))}
      </div>
      {errors.operating_days && <p className="text-xs text-danger">{errors.operating_days}</p>}
    </div>
  );
}

export function FixedBlocksEditor({ values, update, errors }: SectionProps) {
  const blocks = values.fixedBlocks;
  const setBlock = (index: number, changes: Partial<BlockValues>) =>
    update({ fixedBlocks: blocks.map((b, i) => (i === index ? { ...b, ...changes } : b)) });

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium">When is it switched on?</p>
        <p className="text-xs text-muted">{MIDNIGHT_HINT} 00:00–00:00 means all day.</p>
      </div>
      {blocks.map((block, index) => (
        <div key={index} className="flex items-end gap-3">
          <div className="flex-1">
            <Field label={`Period ${index + 1} start`} error={errors[`fixed_blocks.${index}.start_minute`]}>
              {(p) => <TextInput {...p} type="time" step={TIME_STEP_SECONDS} value={block.start} onChange={(e) => setBlock(index, { start: e.target.value })} />}
            </Field>
          </div>
          <div className="flex-1">
            <Field label={`Period ${index + 1} end`} error={errors[`fixed_blocks.${index}.end_minute`]}>
              {(p) => <TextInput {...p} type="time" step={TIME_STEP_SECONDS} value={block.end} onChange={(e) => setBlock(index, { end: e.target.value })} />}
            </Field>
          </div>
          <Button
            variant="ghost"
            aria-label={`Remove period ${index + 1}`}
            disabled={blocks.length === 1}
            onClick={() => update({ fixedBlocks: blocks.filter((_, i) => i !== index) })}
          >
            <Trash2 aria-hidden className="size-4" />
          </Button>
        </div>
      ))}
      {errors.fixed_blocks && <p className="text-xs text-danger">{errors.fixed_blocks}</p>}
      <Button variant="secondary" onClick={() => update({ fixedBlocks: [...blocks, { ...ALL_DAY_BLOCK, start: '', end: '' }] })}>
        <Plus aria-hidden className="size-4" /> Add period
      </Button>
    </div>
  );
}

const HOURS = Array.from({ length: 25 }, (_, h) => h);
const MINUTES = [0, 15, 30, 45];

export function FlexibleFields({ values, update, errors }: SectionProps) {
  const durationInvalid = Boolean(errors['flexible.run_duration_minutes']);
  const timeField = (label: string, key: 'earliestStart' | 'latestEnd' | 'currentStart' | 'preferredStart' | 'preferredEnd', errorKey: string, hint?: string) => (
    <Field label={label} error={errors[errorKey]} {...(hint ? { hint } : {})}>
      {(p) => <TextInput {...p} type="time" step={TIME_STEP_SECONDS} value={values[key]} onChange={(e) => update({ [key]: e.target.value })} />}
    </Field>
  );

  return (
    <div className="space-y-5">
      {errors.flexible && <p className="text-sm text-danger">{errors.flexible}</p>}

      <div>
        <span id="duration-label" className="text-sm font-medium">
          Run duration
        </span>
        <div role="group" aria-labelledby="duration-label" className="mt-1.5 grid grid-cols-2 gap-3">
          <Select
            aria-label="Hours"
            aria-invalid={durationInvalid}
            aria-describedby="duration-message"
            value={values.durationHours}
            onChange={(e) => update({ durationHours: e.target.value })}
          >
            {HOURS.map((h) => (
              <option key={h} value={h}>
                {h} h
              </option>
            ))}
          </Select>
          <Select
            aria-label="Minutes"
            aria-invalid={durationInvalid}
            aria-describedby="duration-message"
            value={values.durationMinutes}
            onChange={(e) => update({ durationMinutes: e.target.value })}
          >
            {MINUTES.map((m) => (
              <option key={m} value={m}>
                {m} min
              </option>
            ))}
          </Select>
        </div>
        <p id="duration-message" className={cn('mt-1.5 text-xs', durationInvalid ? 'text-danger' : 'text-muted')}>
          {errors['flexible.run_duration_minutes'] ?? 'How long one run takes, e.g. a wash cycle.'}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {timeField('Earliest start', 'earliestStart', 'flexible.earliest_start_minute')}
        {timeField('Latest finish', 'latestEnd', 'flexible.latest_end_minute')}
        {timeField('Usual start today', 'currentStart', 'flexible.current_start_minute', 'Your current habit. Savings are measured against it.')}
      </div>
      <p className="-mt-2 text-xs text-muted">The whole run must fit between earliest start and latest finish. {MIDNIGHT_HINT}</p>

      <Checkbox
        label="I have a preferred time"
        description="A soft preference inside the allowed window. The scheduler will try to honour it."
        checked={values.usePreferredWindow}
        onChange={(e) => update({ usePreferredWindow: e.target.checked })}
      />
      {values.usePreferredWindow && (
        <div className="space-y-1.5">
          <div className="grid gap-4 md:grid-cols-2">
            {timeField('Preferred from', 'preferredStart', 'flexible.preferred_start_minute')}
            {timeField('Preferred until', 'preferredEnd', 'flexible.preferred_end_minute')}
          </div>
          {errors['flexible.preferred_window'] && <p className="text-xs text-danger">{errors['flexible.preferred_window']}</p>}
        </div>
      )}

      <Checkbox
        label="Must run without interruption"
        description="Most appliances (washers, dishwashers) cannot pause mid-cycle."
        checked={values.mustBeContiguous}
        onChange={(e) => update({ mustBeContiguous: e.target.checked })}
      />
    </div>
  );
}
