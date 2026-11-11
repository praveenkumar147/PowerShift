import { cn } from '@/lib/cn';

export function Spinner({ className, label = 'Loading' }: { className?: string; label?: string }) {
  return (
    <div
      role="status"
      aria-label={label}
      className={cn('size-6 animate-spin rounded-full border-2 border-border border-t-accent-ink', className)}
    />
  );
}
