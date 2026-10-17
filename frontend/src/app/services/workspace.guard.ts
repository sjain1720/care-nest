import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, finalize, map, of, from, switchMap } from 'rxjs';
import { VisitorProfileService } from './visitor-profile.service';
import { ApiService } from './api.service';
import { WorkspaceService, Workspace } from './workspace.service';

/** Canonical query selectors make refresh/back/deep links restore the same workspace. */
export const exampleWorkspaceGuard: CanActivateFn = (route, state) => {
  const workspace = inject(WorkspaceService), router = inject(Router), api = inject(ApiService);
  const requested = route.queryParamMap.get('workspace');
  const mode = state.url.split('?')[0] === '/upload' && requested !== 'example' ? 'personal'
    : requested === 'personal' || requested === 'example' ? requested : workspace.choice() ?? 'example';
  if (requested !== mode) {
    const url = router.parseUrl(state.url); url.queryParams['workspace'] = mode;
    return url;
  }
  workspace.select(mode);
  workspace.opening.set(true);
  return from(inject(VisitorProfileService).load()).pipe(switchMap(() => api.activateWorkspace(mode))).pipe(map(() => true), catchError(() => of(router.createUrlTree(['/workspace-unavailable']))),
    finalize(() => workspace.opening.set(false)));
};
export const generalWorkspaceGuard: CanActivateFn = (route) => {
  const workspace = inject(WorkspaceService), api = inject(ApiService);
  const requested = route.queryParamMap.get('workspace');
  const mode: Workspace = requested === 'personal' || requested === 'example' ? requested : 'general';
  if (mode !== 'general') workspace.select(mode);
  return from(inject(VisitorProfileService).load()).pipe(switchMap(() => api.activateWorkspace(mode))).pipe(map(() => true), catchError(() => { api.clearWorkspace(); return of(true); }));
};
export const chatWorkspaceGuard: CanActivateFn = (route, state) => {
  if (!inject(WorkspaceService).choice() && !route.queryParamMap.get('workspace')) {
    inject(WorkspaceService).choosing.set(true); return generalWorkspaceGuard(route, state);
  }
  const requested = route.queryParamMap.get('workspace');
  return requested === 'personal' || requested === 'example'
    ? exampleWorkspaceGuard(route, state) : generalWorkspaceGuard(route, state);
};
