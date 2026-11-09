import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  message: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, title, message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-border bg-surface px-6 py-16 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-surface-raised text-muted">
        <Icon aria-hidden className="size-6" />
      </div>
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-1 max-w-md text-sm text-muted">{message}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
