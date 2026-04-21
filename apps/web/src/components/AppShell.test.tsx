import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  RouterProvider,
  createRouter,
  createRootRoute,
  createRoute,
  createMemoryHistory,
} from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { AppShell } from './AppShell';

function renderShell() {
  const rootRoute = createRootRoute({
    component: () => (
      <AppShell>
        <div data-testid="content">content</div>
      </AppShell>
    ),
  });
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => null,
  });
  const modelsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/models',
    component: () => null,
  });
  const history = createMemoryHistory({ initialEntries: ['/'] });
  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute, modelsRoute]),
    history,
    context: { queryClient: new QueryClient() },
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe('AppShell', () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('renders the header brand', async () => {
    globalThis.fetch = (async () => new Response('', { status: 401 })) as unknown as typeof fetch;
    renderShell();
    expect(await screen.findByText('Quant Platform')).toBeInTheDocument();
    expect(await screen.findByTestId('content')).toBeInTheDocument();
  });

  it('shows Sign in when unauthenticated', async () => {
    globalThis.fetch = (async () => new Response('', { status: 401 })) as unknown as typeof fetch;
    renderShell();
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows user email and Sign out when authenticated', async () => {
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          sub: 'qp|mock|admin',
          email: 'admin@example.test',
          name: 'Admin',
          roles: ['admin', 'quant'],
          tenant_id: 'acme',
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )) as unknown as typeof fetch;
    renderShell();
    expect(await screen.findByText('admin@example.test')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /sign out/i })).toBeInTheDocument();
    expect(await screen.findByText('admin')).toBeInTheDocument();
  });
});
