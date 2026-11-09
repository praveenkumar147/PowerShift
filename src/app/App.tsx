import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { createHashRouter, RouterProvider } from 'react-router';
import { BackendProvider } from '@/api/BackendProvider';
import { routes } from '@/app/routes';
import { ThemeProvider } from '@/app/theme/ThemeProvider';

// Hash routing (#/appliances) works when the app is loaded from local files in
// the packaged desktop build, where there is no web server to rewrite URLs.
const router = createHashRouter(routes);

export function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          // Local backend: data only changes when this app changes it.
          queries: { refetchOnWindowFocus: false, retry: 1 },
        },
      }),
  );

  return (
    <ThemeProvider>
      <BackendProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </BackendProvider>
    </ThemeProvider>
  );
}
