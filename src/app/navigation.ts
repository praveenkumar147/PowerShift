import {
  BarChart3,
  CalendarClock,
  FileText,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Plug,
  ReceiptText,
  Settings,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
}

/** The sidebar. Each path has a page in routes.tsx. */
export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/appliances', label: 'Appliances', icon: Plug },
  { path: '/tariff', label: 'Electricity Tariff', icon: ReceiptText },
  { path: '/energy', label: 'Energy Analysis', icon: BarChart3 },
  { path: '/peak-load', label: 'Peak Load', icon: Gauge },
  { path: '/scheduler', label: 'Smart Scheduler', icon: CalendarClock },
  { path: '/simulation', label: 'Simulation Lab', icon: FlaskConical },
  { path: '/reports', label: 'Reports', icon: FileText },
  { path: '/settings', label: 'Settings', icon: Settings },
];
