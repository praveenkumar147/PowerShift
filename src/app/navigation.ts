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
  description: string;
  /** Development stage in which this module is implemented. */
  stage: number;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/', label: 'Overview', icon: LayoutDashboard, stage: 1, description: 'Household energy at a glance.' },
  { path: '/appliances', label: 'Appliances', icon: Plug, stage: 2, description: 'Add and configure the appliances in your home.' },
  { path: '/tariff', label: 'Electricity Tariff', icon: ReceiptText, stage: 3, description: 'Configure flat, time-of-use and slab tariffs.' },
  { path: '/energy', label: 'Energy Analysis', icon: BarChart3, stage: 3, description: 'Estimated consumption and cost breakdowns.' },
  { path: '/peak-load', label: 'Peak Load', icon: Gauge, stage: 4, description: 'Hourly demand, peaks and load-limit warnings.' },
  { path: '/scheduler', label: 'Smart Scheduler', icon: CalendarClock, stage: 5, description: 'Optimized appliance schedules using CP-SAT.' },
  { path: '/simulation', label: 'Simulation Lab', icon: FlaskConical, stage: 6, description: 'What-if scenarios without touching your real data.' },
  { path: '/reports', label: 'Reports', icon: FileText, stage: 7, description: 'CSV and PDF reports.' },
  { path: '/settings', label: 'Settings', icon: Settings, stage: 7, description: 'Preferences, backups and data management.' },
];
