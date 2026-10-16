import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, finalize, map, of } from 'rxjs';
import { ApiService } from './api.service';
import { WorkspaceService } from './workspace.service';

export const exampleWorkspaceGuard: CanActivateFn = () => {
  const workspace = inject(WorkspaceService);
  const router = inject(Router);
  workspace.mode.set('example');
  workspace.opening.set(true);
  return inject(ApiService).ensureExampleWorkspace().pipe(
    map(() => true),
    catchError(() => {
      workspace.mode.set('general');
      return of(router.createUrlTree(['/workspace-unavailable']));
    }),
    finalize(() => workspace.opening.set(false)),
  );
};

export const generalWorkspaceGuard: CanActivateFn = () => {
  inject(WorkspaceService).mode.set('general');
  return true;
};

export const chatWorkspaceGuard: CanActivateFn = (route, state) => {
  return route.queryParamMap.get('workspace') === 'example'
    ? exampleWorkspaceGuard(route, state) : generalWorkspaceGuard(route, state);
};
