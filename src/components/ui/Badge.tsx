import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type Tone = 'neutral' | 'accent' | 'warning';

const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-raised text-muted border-border',
  accent: 'bg-accent-soft text-accent-ink border-accent-ink/25',
  warning: 'bg-warning/10 text-warning border-warning/25',
};

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium', TONES[tone])}>{children}</span>
  );
}
