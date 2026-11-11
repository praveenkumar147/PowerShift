import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { useApiClient } from '@/api/BackendProvider';
import { useTheme, type ThemePreference } from '@/app/theme/ThemeProvider';

interface Preferences {
  theme: ThemePreference;
}

/**
 * Keeps the theme in the database.
 *
 * The browser's local storage still applies the theme instantly at startup (no flash of the
 * wrong colours). Once the backend answers, the database wins: it also survives a restored
 * backup or a reinstall of the window. After that, every change the user makes is saved.
 * If the backend cannot be reached, the choice still works for this session.
 */
export function ThemeSync() {
  const client = useApiClient();
  const { preference, setPreference } = useTheme();
  const stored = useQuery({ queryKey: ['settings', 'preferences'], queryFn: () => client.get<Preferences>('/api/settings/preferences') });
  const save = useMutation({ mutationFn: (theme: ThemePreference) => client.send<Preferences>('PUT', '/api/settings/preferences', { theme }) });
  const known = useRef<ThemePreference | null>(null);

  const { mutate } = save;
  const databaseTheme = stored.data?.theme;
  useEffect(() => {
    if (databaseTheme === undefined) return;
    if (known.current === null) {
      // First answer from the database: adopt it.
      known.current = databaseTheme;
      if (databaseTheme !== preference) setPreference(databaseTheme);
    } else if (preference !== known.current) {
      // The user chose something new: save it.
      known.current = preference;
      mutate(preference);
    }
  }, [databaseTheme, preference, setPreference, mutate]);

  return null;
}
