import type { ReactElement } from 'react';
import type { RouteObject } from 'react-router';
import { AppLayout } from '@/app/layout/AppLayout';
import { NAV_ITEMS } from '@/app/navigation';
import { AppliancesPage } from '@/features/appliances/AppliancesPage';
import { EnergyPage } from '@/features/energy/EnergyPage';
import { OverviewPage } from '@/features/overview/OverviewPage';
import { ModulePendingPage } from '@/features/pending/ModulePendingPage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { TariffsPage } from '@/features/tariffs/TariffsPage';

/** Pages that exist so far; every other nav item shows the pending page. */
const IMPLEMENTED_PAGES: Record<string, ReactElement> = {
  '/': <OverviewPage />,
  '/appliances': <AppliancesPage />,
  '/tariff': <TariffsPage />,
  '/energy': <EnergyPage />,
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
