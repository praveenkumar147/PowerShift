import type { RouteObject } from 'react-router';
import { AppLayout } from '@/app/layout/AppLayout';
import { AppliancesPage } from '@/features/appliances/AppliancesPage';
import { EnergyPage } from '@/features/energy/EnergyPage';
import { OverviewPage } from '@/features/overview/OverviewPage';
import { PeakLoadPage } from '@/features/peak-load/PeakLoadPage';
import { ReportsPage } from '@/features/reports/ReportsPage';
import { SchedulerPage } from '@/features/scheduler/SchedulerPage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { SimulationPage } from '@/features/simulation/SimulationPage';
import { TariffsPage } from '@/features/tariffs/TariffsPage';

/** The path of each page matches `NAV_ITEMS` in navigation.ts (the sidebar). */
export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <OverviewPage /> },
      { path: '/appliances', element: <AppliancesPage /> },
      { path: '/tariff', element: <TariffsPage /> },
      { path: '/energy', element: <EnergyPage /> },
      { path: '/peak-load', element: <PeakLoadPage /> },
      { path: '/scheduler', element: <SchedulerPage /> },
      { path: '/simulation', element: <SimulationPage /> },
      { path: '/reports', element: <ReportsPage /> },
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
];
