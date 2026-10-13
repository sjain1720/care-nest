import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', title: 'CareNest', loadComponent: () => import('./pages/home/home.component').then((m) => m.HomeComponent) },
  { path: 'upload', title: 'Add documents · CareNest', loadComponent: () => import('./pages/upload/upload.component').then((m) => m.UploadComponent) },
  { path: 'policy', title: 'My policy · CareNest', loadComponent: () => import('./pages/policy/policy.component').then((m) => m.PolicyComponent) },
  { path: 'ask', title: 'Ask CareNest', loadComponent: () => import('./pages/ask/ask.component').then((m) => m.AskComponent) },
  { path: 'case', title: 'My claim · CareNest', loadComponent: () => import('./pages/case/case.component').then((m) => m.CaseComponent) },
  { path: 'case/bill', title: 'Check my bill · CareNest', loadComponent: () => import('./pages/bill-check/bill-check.component').then((m) => m.BillCheckComponent) },
  { path: 'case/settlement', title: 'Why money was cut · CareNest', loadComponent: () => import('./pages/settlement/settlement.component').then((m) => m.SettlementComponent) },
  { path: 'case/letter', title: 'Write to the insurer · CareNest', loadComponent: () => import('./pages/letter/letter.component').then((m) => m.LetterComponent) },
  { path: 'case/reply', title: "Insurer's reply · CareNest", loadComponent: () => import('./pages/reply/reply.component').then((m) => m.ReplyComponent) },
  { path: 'case/query', title: "Insurer's question · CareNest", loadComponent: () => import('./pages/query-helper/query-helper.component').then((m) => m.QueryHelperComponent) },
  { path: 'status', title: 'Demo and live settings · CareNest', loadComponent: () => import('./pages/status/status.component').then((m) => m.StatusComponent) },
  { path: '**', redirectTo: '' },
];
