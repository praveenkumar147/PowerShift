import { Zap } from 'lucide-react';
import { NavLink } from 'react-router';
import { NAV_ITEMS } from '@/app/navigation';
import { ThemeSwitcher } from '@/app/theme/ThemeSwitcher';
import { cn } from '@/lib/cn';

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex size-8 items-center justify-center rounded-md bg-accent text-accent-fg">
          <Zap aria-hidden className="size-4.5" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">PowerShift</p>
          <p className="text-xs text-muted">Energy optimization</p>
        </div>
      </div>

      <nav aria-label="Main" className="flex-1 space-y-0.5 px-3">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-accent-soft font-medium text-accent'
                  : 'text-muted hover:bg-surface-raised hover:text-fg',
              )
            }
          >
            <Icon aria-hidden className="size-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3">
        <ThemeSwitcher />
      </div>
    </aside>
  );
}
