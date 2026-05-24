import { RenderMode, ServerRoute } from '@angular/ssr';

export const serverRoutes: ServerRoute[] = [
  {
    path: '',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'forgot-password',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'requirements',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'requirements/create',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'requirements/:id',
    renderMode: RenderMode.Server
  },
  {
    path: 'users',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'test-cases',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'test-cases/create',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'test-cases/import',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'test-cases/:id',
    renderMode: RenderMode.Server
  },
  {
    path: 'design-tickets',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'design-tickets/create',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'design-tickets/:id',
    renderMode: RenderMode.Server
  },
  {
    path: 'split-view',
    renderMode: RenderMode.Prerender
  },
  {
    path: '**',
    renderMode: RenderMode.Server
  }
];
