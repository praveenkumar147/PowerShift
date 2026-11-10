import { Play } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/inputs';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { PRIORITY_LABELS, type OptimizationRequest, type Priority, type StartStep } from '@/features/scheduler/types';

const GOALS = (['cost', 'balanced', 'peak'] as const).map((value) => ({ value, label: PRIORITY_LABELS[value] }));

const GOAL_HELP: Record<Priority, string> = {
  cost: 'Finds the cheapest valid schedule. If several are equally cheap, picks the one with the lowest peak.',
  balanced: 'Weighs cost and peak together, each relative to your current schedule.',
  peak: 'Finds the schedule with the lowest peak demand. If several tie, picks the cheapest.',
};

const TIME_LIMITS = [5, 10, 30, 60];

interface RunControlsProps {
  running: boolean;
  error: string | null;
  onRun: (request: OptimizationRequest) => void;
}

export function RunControls({ running, error, onRun }: RunControlsProps) {
  const [priority, setPriority] = useState<Priority>('balanced');
  const [weight, setWeight] = useState(50);
  const [step, setStep] = useState<StartStep>(60);
  const [timeLimit, setTimeLimit] = useState(10);

  return (
    <Card title="Optimize" description="Choose a goal. The scheduler only moves flexible appliances, inside the windows you allowed.">
      <div className="space-y-5">
        <div className="space-y-2">
          <SegmentedControl label="Goal" options={GOALS} value={priority} onChange={setPriority} />
          <p className="text-xs text-muted">{GOAL_HELP[priority]}</p>
        </div>

        {priority === 'balanced' && (
          <div>
            <label htmlFor="balance-weight" className="block text-sm font-medium">
              Balance
            </label>
            <input
              id="balance-weight"
              type="range"
              min={0}
              max={100}
              step={5}
              value={weight}
              onChange={(e) => setWeight(Number(e.target.value))}
              aria-valuetext={`Cost ${weight}%, peak ${100 - weight}%`}
              className="mt-2 w-full accent-[var(--ps-accent)]"
            />
            <div className="flex justify-between text-xs text-muted">
              <span>Peak matters most</span>
              <span className="font-medium text-fg tabular-nums">
                Cost {weight}% · Peak {100 - weight}%
              </span>
              <span>Cost matters most</span>
            </div>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Start times" hint="Finer steps can find better schedules but take longer.">
            {(p) => (
              <Select {...p} value={step} onChange={(e) => setStep(Number(e.target.value) as StartStep)}>
                <option value={60}>On the hour</option>
                <option value={30}>Every 30 minutes</option>
                <option value={15}>Every 15 minutes</option>
              </Select>
            )}
          </Field>
          <Field label="Time limit" hint="If it runs out, the best schedule found so far is shown, marked as not proven optimal.">
            {(p) => (
              <Select {...p} value={timeLimit} onChange={(e) => setTimeLimit(Number(e.target.value))}>
                {TIME_LIMITS.map((seconds) => (
                  <option key={seconds} value={seconds}>
                    {seconds} seconds
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        {error && (
          <p role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
            {error}
          </p>
        )}

        <Button
          disabled={running}
          onClick={() => onRun({ priority, balance_weight: weight, start_step_minutes: step, time_limit_seconds: timeLimit })}
        >
          <Play aria-hidden className="size-4" /> {running ? 'Optimizing…' : 'Optimize schedule'}
        </Button>
      </div>
    </Card>
  );
}
