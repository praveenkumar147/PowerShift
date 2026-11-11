import { useId, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface CardProps {
  title?: string;
  description?: string | undefined;
  className?: string | undefined;
  children: ReactNode;
}

export function Card({ title, description, className, children }: CardProps) {
  const headingId = useId();
  return (
    // A titled card is a labelled region, so screen-reader users can jump between cards.
    <section aria-labelledby={title ? headingId : undefined} className={cn('rounded-xl border border-border bg-surface p-6 shadow-sm', className)}>
      {title && (
        <header className="mb-4">
          <h2 id={headingId} className="text-base font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
        </header>
      )}
      {children}
    </section>
  );
}
