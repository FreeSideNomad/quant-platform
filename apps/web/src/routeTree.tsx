import { createRootRoute, createRoute, Outlet } from '@tanstack/react-router';
import { AppShell } from './components/AppShell';
import { HomePage } from './routes/Home';
import { ModelsPage } from './routes/Models';
import { ModelDetailPage } from './routes/ModelDetail';

const rootRoute = createRootRoute({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
});

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: HomePage,
});

const modelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models',
  component: ModelsPage,
});

const modelDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models/$modelId',
  component: () => {
    const { modelId } = modelDetailRoute.useParams();
    return <ModelDetailPage modelId={modelId} />;
  },
});

export const routeTree = rootRoute.addChildren([homeRoute, modelsRoute, modelDetailRoute]);
