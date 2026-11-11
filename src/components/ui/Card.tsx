import { useId, type CSSProperties, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface CardProps {
  title?: string;
  description?: string | undefined;
  className?: string | undefined;
  children: ReactNode;
  /** Position in a group of cards: later cards appear a moment after earlier ones. */
  index?: number;
  /** Gently floats up and down. Use on one or two featured cards per page, never on all of them. */
  floating?: boolean;
  /** Lifts slightly on hover (for cards that are clickable or that you want to feel tactile). */
  interactive?: boolean;
}

/** Staggered entrance delay in milliseconds: 60 ms per card, capped so nothing waits long. */
export function revealDelay(index: number): CSSProperties {
  return { animationDelay: `${Math.min(index, 8) * 60}ms` };
}

export function Card({ title, description, className, children, index = 0, floating = false, interactive = false }: CardProps) {
  const headingId = useId();
  return (
    // A titled card is a labelled region, so screen-reader users can jump between cards.
    <section
      aria-labelledby={title ? headingId : undefined}
      style={revealDelay(index)}
      className={cn(
        'animate-rise rounded-card border border-border bg-surface p-6 shadow-card',
        interactive && 'transition-[transform,border-color,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-accent-ink/40 hover:shadow-float',
        floating && 'motion-safe:animate-float',
        className,
      )}
    >
      {title && (
        <header className="mb-4">
          <h2 id={headingId} className="text-base font-semibold">
            {title}
          </h2>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
        </header>
      )}
      {children}
    </section>
  );
}
