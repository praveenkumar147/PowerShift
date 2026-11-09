import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme, type ThemePreference } from '@/app/theme/ThemeProvider';
import { SegmentedControl, type SegmentOption } from '@/components/ui/SegmentedControl';

const OPTIONS: ReadonlyArray<SegmentOption<ThemePreference>> = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

export function ThemeSwitcher() {
  const { preference, setPreference } = useTheme();
  return (
    <SegmentedControl label="Theme" size="sm" options={OPTIONS} value={preference} onChange={setPreference} />
  );
}
