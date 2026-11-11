import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { BackendProvider } from '@/api/BackendProvider';
import type { BackendConnection } from '@/api/connection';
import { preloadPages, routes } from '@/app/routes';
import { ThemeProvider } from '@/app/theme/ThemeProvider';

// Pages are lazy-loaded in the app; tests load them up front so they appear immediately.
await preloadPages();

export const TEST_CONNECTION: BackendConnection = { baseUrl: 'http://backend.test', token: 'test-token' };

const connectInstantly = () => Promise.resolve(TEST_CONNECTION);

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

/** Renders a component with theme, backend and query providers. */
export function renderWithProviders(ui: ReactElement) {
  return render(
    <ThemeProvider>
      <BackendProvider connect={connectInstantly}>
        <QueryClientProvider client={makeQueryClient()}>{ui}</QueryClientProvider>
      </BackendProvider>
    </ThemeProvider>,
  );
}

/** Renders the full app shell at a given route. */
export function renderApp(initialPath = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] });
  return renderWithProviders(<RouterProvider router={router} />);
}

/** For client unit tests that mock fetch directly. */
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
