import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

// Primary is the lime fill with black text (17.8:1). Only one should dominate a view.
const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:brightness-95 active:brightness-90',
  secondary: 'border border-border bg-surface-raised text-fg hover:border-muted/60',
  ghost: 'text-muted hover:bg-surface-raised hover:text-fg',
  danger: 'bg-danger text-danger-fg hover:brightness-95 active:brightness-90',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = 'primary', className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-control px-4 py-2 text-sm font-medium',
        'transition-[background-color,border-color,filter,transform] duration-150 active:scale-[0.98]',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink',
        'disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100',
        VARIANT_CLASSES[variant],
        className,
      )}
      {...props}
    />
  );
}
