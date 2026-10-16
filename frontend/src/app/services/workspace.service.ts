import { Injectable, inject, signal } from '@angular/core';
import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { map } from 'rxjs';

export type Workspace = 'general' | 'example';

/** A selector, never a user/owner ID. The backend derives an owned child identity. */
@Injectable({ providedIn: 'root' })
export class WorkspaceService {
  readonly mode = signal<Workspace>('general');
  readonly opening = signal(false);

  url(url: string, mode: Workspace = this.mode()): string {
    if (!url.startsWith('/api/')) return url;
    const [path, hash] = url.split('#', 2);
    const [base, search] = path.split('?', 2);
    const params = new URLSearchParams(search);
    params.set('workspace', mode);
    return `${base}?${params}${hash ? '#' + hash : ''}`;
  }

  links<T>(value: T, mode: Workspace): T {
    if (Array.isArray(value)) return value.map((item) => this.links(item, mode)) as T;
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
        key === 'docUrl' && typeof item === 'string' ? this.url(item, mode) : this.links(item, mode),
      ])) as T;
    }
    return value;
  }
}

export const workspaceInterceptor: HttpInterceptorFn = (request, next) => {
  const workspace = inject(WorkspaceService);
  const mode: Workspace = request.urlWithParams.includes('workspace=example') ? 'example'
    : request.urlWithParams.includes('workspace=general') ? 'general' : workspace.mode();
  const scoped = request.url.startsWith('/api/')
    ? request.clone({ params: request.params.set('workspace', mode) }) : request;
  return next(scoped).pipe(map((event) => event instanceof HttpResponse && request.url.startsWith('/api/')
    ? event.clone({ body: workspace.links(event.body, mode) }) : event));
};
