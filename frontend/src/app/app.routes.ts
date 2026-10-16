import { Routes } from '@angular/router';
import { chatWorkspaceGuard, exampleWorkspaceGuard, generalWorkspaceGuard } from './services/workspace.guard';

export const routes: Routes = [
  { path: '', title: 'Welcome · CareNest', canActivate: [generalWorkspaceGuard], loadComponent: () => import('./pages/home/home.component').then((m) => m.HomeComponent) },
  { path: 'dashboard', title: "Ravi's dashboard · CareNest", canActivate: [exampleWorkspaceGuard], data: { dashboard: true }, loadComponent: () => import('./pages/case/case.component').then((m) => m.CaseComponent) },
  { path: 'workspace-unavailable', title: 'Dashboard unavailable · CareNest', canActivate: [generalWorkspaceGuard], loadComponent: () => import('./pages/home/workspace-unavailable.component').then((m) => m.WorkspaceUnavailableComponent) },
  { path: 'upload', title: 'Add documents · CareNest', canActivate: [exampleWorkspaceGuard], loadComponent: () => import('./pages/upload/upload.component').then((m) => m.UploadComponent) },
  { path: 'policy', title: 'My policy · CareNest', canActivate: [exampleWorkspaceGuard], loadComponent: () => import('./pages/policy/policy.component').then((m) => m.PolicyComponent) },
  { path: 'ask', title: 'Ask CareNest', canActivate: [chatWorkspaceGuard], runGuardsAndResolvers: 'paramsOrQueryParamsChange', loadComponent: () => import('./pages/ask/ask.component').then((m) => m.AskComponent) },
  { path: 'case', canActivate: [exampleWorkspaceGuard], title: 'My claim · CareNest', loadComponent: () => import('./pages/case/case.component').then((m) => m.CaseComponent) },
  { path: 'case/bill', canActivate: [exampleWorkspaceGuard], title: 'Check my bill · CareNest', loadComponent: () => import('./pages/bill-check/bill-check.component').then((m) => m.BillCheckComponent) },
  { path: 'case/settlement', canActivate: [exampleWorkspaceGuard], title: 'Why money was cut · CareNest', loadComponent: () => import('./pages/settlement/settlement.component').then((m) => m.SettlementComponent) },
  { path: 'case/letter', canActivate: [exampleWorkspaceGuard], title: 'Write to the insurer · CareNest', loadComponent: () => import('./pages/letter/letter.component').then((m) => m.LetterComponent) },
  { path: 'case/reply', canActivate: [exampleWorkspaceGuard], title: "Insurer's reply · CareNest", loadComponent: () => import('./pages/reply/reply.component').then((m) => m.ReplyComponent) },
  { path: 'case/query', canActivate: [exampleWorkspaceGuard], title: "Insurer's question · CareNest", loadComponent: () => import('./pages/query-helper/query-helper.component').then((m) => m.QueryHelperComponent) },
  { path: 'status', canActivate: [exampleWorkspaceGuard], title: 'Demo and live settings · CareNest', loadComponent: () => import('./pages/status/status.component').then((m) => m.StatusComponent) },
  { path: '**', redirectTo: '' },
];
