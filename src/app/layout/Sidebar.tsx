import { PanelLeftClose, PanelLeftOpen, Zap } from 'lucide-react';
import { useState } from 'react';
import { NavLink } from 'react-router';
import { NAV_ITEMS } from '@/app/navigation';
import { ThemeSwitcher } from '@/app/theme/ThemeSwitcher';
import { cn } from '@/lib/cn';

const STORAGE_KEY = 'powershift.sidebar';

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'collapsed';
  } catch {
    return false; // storage unavailable: start expanded
  }
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggle = () => {
    setCollapsed(!collapsed);
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? 'expanded' : 'collapsed');
    } catch {
      // The choice still applies for this session.
    }
  };

  return (
    <aside
      className={cn(
        'relative z-10 flex shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200 ease-out',
        collapsed ? 'w-[68px]' : 'w-60',
      )}
    >
      <div className={cn('flex items-center py-5', collapsed ? 'justify-center px-0' : 'gap-3 px-5')}>
        <div className="flex size-9 shrink-0 items-center justify-center rounded-control bg-accent text-accent-fg">
          <Zap aria-hidden className="size-5" strokeWidth={2.5} />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="font-display text-[0.95rem] font-semibold leading-tight tracking-tight">PowerShift</p>
            <p className="text-xs text-muted">Energy optimization</p>
          </div>
        )}
      </div>

      <nav aria-label="Main" className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center rounded-control py-2.5 text-sm transition-colors duration-150',
                collapsed ? 'justify-center px-0' : 'gap-3 px-3',
                isActive ? 'bg-surface-raised font-medium text-accent-ink' : 'text-muted hover:bg-surface-raised hover:text-fg',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span aria-hidden className="absolute -left-3 top-2 bottom-2 w-[3px] animate-fade rounded-r-full bg-accent" />}
                <Icon aria-hidden className="size-[18px] shrink-0 transition-transform duration-150 group-hover:scale-110" />
                <span className={collapsed ? 'sr-only' : undefined}>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-3 border-t border-border p-3">
        {!collapsed && <ThemeSwitcher />}
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          className={cn(
            'flex w-full items-center rounded-control py-2 text-xs text-muted transition-colors hover:bg-surface-raised hover:text-fg',
            'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink',
            collapsed ? 'justify-center' : 'gap-2 px-3',
          )}
        >
          {collapsed ? <PanelLeftOpen aria-hidden className="size-4" /> : <PanelLeftClose aria-hidden className="size-4" />}
          {!collapsed && 'Collapse'}
        </button>
      </div>
    </aside>
  );
}
