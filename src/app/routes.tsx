import { lazy } from 'react';
import type { RouteObject } from 'react-router';
import { AppLayout } from '@/app/layout/AppLayout';

// Each page is its own chunk, downloaded the first time it is opened. This keeps the first
// screen small: the chart library only loads with the pages that draw charts.
const loaders = {
  OverviewPage: () => import('@/features/overview/OverviewPage').then((m) => ({ default: m.OverviewPage })),
  AppliancesPage: () => import('@/features/appliances/AppliancesPage').then((m) => ({ default: m.AppliancesPage })),
  TariffsPage: () => import('@/features/tariffs/TariffsPage').then((m) => ({ default: m.TariffsPage })),
  EnergyPage: () => import('@/features/energy/EnergyPage').then((m) => ({ default: m.EnergyPage })),
  PeakLoadPage: () => import('@/features/peak-load/PeakLoadPage').then((m) => ({ default: m.PeakLoadPage })),
  SchedulerPage: () => import('@/features/scheduler/SchedulerPage').then((m) => ({ default: m.SchedulerPage })),
  SimulationPage: () => import('@/features/simulation/SimulationPage').then((m) => ({ default: m.SimulationPage })),
  ReportsPage: () => import('@/features/reports/ReportsPage').then((m) => ({ default: m.ReportsPage })),
  SettingsPage: () => import('@/features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })),
};

const [OverviewPage, AppliancesPage, TariffsPage, EnergyPage, PeakLoadPage, SchedulerPage, SimulationPage, ReportsPage, SettingsPage] = [
  lazy(loaders.OverviewPage),
  lazy(loaders.AppliancesPage),
  lazy(loaders.TariffsPage),
  lazy(loaders.EnergyPage),
  lazy(loaders.PeakLoadPage),
  lazy(loaders.SchedulerPage),
  lazy(loaders.SimulationPage),
  lazy(loaders.ReportsPage),
  lazy(loaders.SettingsPage),
];

/** Downloads every page ahead of time (used by tests, so pages appear without a loading step). */
export async function preloadPages(): Promise<void> {
  await Promise.all(Object.values(loaders).map((load) => load()));
}

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
