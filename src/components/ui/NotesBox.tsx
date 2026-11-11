import { Info } from 'lucide-react';

/** The assumptions behind the numbers on a page, always visible below the figures. */
export function NotesBox({ notes, title = 'How these figures are calculated' }: { notes: string[]; title?: string }) {
  return (
    <section aria-label={title} className="rounded-card border border-border bg-surface-raised p-4 text-sm text-muted">
      <p className="mb-2 flex items-center gap-2 font-medium text-fg">
        <Info aria-hidden className="size-4" /> {title}
      </p>
      <ul className="list-disc space-y-1 pl-5">
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </section>
  );
}
