import type { ReactElement } from 'react';
import type { RouteObject } from 'react-router';
import { AppLayout } from '@/app/layout/AppLayout';
import { NAV_ITEMS } from '@/app/navigation';
import { OverviewPage } from '@/features/overview/OverviewPage';
import { ModulePendingPage } from '@/features/pending/ModulePendingPage';

/** Pages that exist so far; every other nav item shows the pending page. */
const IMPLEMENTED_PAGES: Record<string, ReactElement> = {
  '/': <OverviewPage />,
};

export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: NAV_ITEMS.map((item) => ({
      path: item.path,
      element: IMPLEMENTED_PAGES[item.path] ?? <ModulePendingPage item={item} />,
    })),
  },
];
