import type { ReactElement } from 'react';
import type { RouteObject } from 'react-router';
import { AppLayout } from '@/app/layout/AppLayout';
import { NAV_ITEMS } from '@/app/navigation';
import { AppliancesPage } from '@/features/appliances/AppliancesPage';
import { OverviewPage } from '@/features/overview/OverviewPage';
import { ModulePendingPage } from '@/features/pending/ModulePendingPage';
import { SettingsPage } from '@/features/settings/SettingsPage';

/** Pages that exist so far; every other nav item shows the pending page. */
const IMPLEMENTED_PAGES: Record<string, ReactElement> = {
  '/': <OverviewPage />,
  '/appliances': <AppliancesPage />,
  '/settings': <SettingsPage />,
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
