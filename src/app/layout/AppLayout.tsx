import { Suspense, useEffect, useRef } from 'react';
import { Outlet, useLocation } from 'react-router';
import { NAV_ITEMS } from '@/app/navigation';
import { Sidebar } from '@/app/layout/Sidebar';
import { ThemeSync } from '@/app/theme/ThemeSync';
import { Spinner } from '@/components/ui/Spinner';

export function AppLayout() {
  const { pathname } = useLocation();
  const main = useRef<HTMLElement>(null);
  const firstPage = useRef(true);

  // Name the window after the page, and after moving to another page put keyboard and
  // screen-reader focus at the top of it (a single-page app has no page load to do that).
  useEffect(() => {
    const label = NAV_ITEMS.find((item) => item.path === pathname)?.label;
    document.title = label ? `${label} · PowerShift` : 'PowerShift';
    if (firstPage.current) firstPage.current = false;
    else main.current?.focus();
  }, [pathname]);

  return (
    <div className="flex h-full">
      <ThemeSync />
      {/* A button, not a #link: the app uses hash routing, where #main would mean a page called "main". */}
      <button
        type="button"
        onClick={() => main.current?.focus()}
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-accent-fg"
      >
        Skip to main content
      </button>
      <Sidebar />
      <main ref={main} id="main" tabIndex={-1} className="flex-1 overflow-y-auto focus:outline-none">
        <div className="mx-auto max-w-6xl px-8 py-8">
          <Suspense fallback={<Spinner label="Loading page" />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
