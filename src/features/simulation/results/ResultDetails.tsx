import { NotesBox } from '@/components/ui/NotesBox';
import { ScheduleTable, ValidationCard } from '@/features/scheduler/ResultView';
import type { SimulationResult } from '@/features/simulation/types';
import type { TimeFormat } from '@/lib/time';

/** The scheduling outcome of one scenario run, in full. */
export function ResultDetails({ result, timeFormat }: { result: SimulationResult; timeFormat: TimeFormat }) {
  const headline = !result.status
    ? 'Scheduling was not attempted'
    : result.schedule_valid
      ? result.proven_optimal
        ? 'Optimal schedule found and verified'
        : 'Valid schedule found, not proven optimal'
      : 'No valid schedule';
  return (
    <div className="space-y-4 border-t border-border pt-4">
      <p className="text-sm">
        <span className="font-medium">{headline}.</span>{' '}
        {result.optimization_note && <span className="text-muted">{result.optimization_note}</span>}
      </p>

      {result.diagnostics.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {result.diagnostics.map((d) => (
            <li key={d.code + d.message}>{d.message}</li>
          ))}
        </ul>
      )}

      {result.schedule_valid && result.items.length > 0 && <ScheduleTable items={result.items} timeFormat={timeFormat} />}
      {result.validation.length > 0 && <ValidationCard checks={result.validation} />}
      <NotesBox notes={result.notes} title="About this result" />
    </div>
  );
}
