import { Routes } from '@angular/router';
export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/overview').then((m) => m.OverviewPage),
    title: 'Overview · Signal',
  },
  {
    path: 'brands/new',
    loadComponent: () => import('./features/brand-form').then((m) => m.BrandFormPage),
    title: 'Add brand · Signal',
  },
  {
    path: 'brands/:id/edit',
    loadComponent: () => import('./features/brand-form').then((m) => m.BrandFormPage),
    title: 'Edit brand · Signal',
  },
  {
    path: 'brands/:id/compare',
    loadComponent: () => import('./features/compare').then((m) => m.ComparePage),
    title: 'Compare · Signal',
  },
  {
    path: 'brands/:id',
    loadComponent: () => import('./features/brand-detail').then((m) => m.BrandDetailPage),
    title: 'Brand workspace · Signal',
  },
  {
    path: 'runs/:id',
    loadComponent: () => import('./features/run').then((m) => m.RunPage),
    title: 'Analysis · Signal',
  },
  {
    path: '**',
    loadComponent: () => import('./features/not-found').then((m) => m.NotFoundPage),
    title: 'Page not found · Signal',
  },
];
