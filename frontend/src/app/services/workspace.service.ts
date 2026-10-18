import { VisitorProfileService } from './visitor-profile.service';
import { Injectable, inject, signal } from '@angular/core';
import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { map } from 'rxjs';

export type Workspace = 'general' | 'personal' | 'example';
export type DocumentWorkspace = 'personal' | 'example';
const CHOICE_KEY = 'carenest.workspace.choice';
function savedChoice(): DocumentWorkspace | null {
  try { const value = sessionStorage.getItem(CHOICE_KEY); return value === 'personal' || value === 'example' ? value : null; }
  catch { return null; }
}

/** Selectors are not owner IDs. Personal uses the browser owner; example uses its owned child. */
@Injectable({ providedIn: 'root' })
export class WorkspaceService {
  readonly profile = inject(VisitorProfileService);
  readonly choice = signal<DocumentWorkspace | null>(savedChoice());
  readonly mode = signal<Workspace>('general');
  readonly opening = signal(false);
  readonly choosing = signal(false);
  readonly label = () => this.mode() === 'example' ? `${this.profile.name() || 'Your'}${this.profile.name() ? "'s" : ''} example` : this.mode() === 'personal' ? 'My documents' : 'General questions';
  select(mode: DocumentWorkspace): void {
    this.choice.set(mode);
    try { sessionStorage.setItem(CHOICE_KEY, mode); } catch { /* storage disabled */ }
  }
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
  const selector = new URL(request.urlWithParams, location.origin).searchParams.get('workspace');
  const mode: Workspace = selector === 'example' || selector === 'personal' || selector === 'general' ? selector : workspace.mode();
  const scoped = request.url.startsWith('/api/') ? request.clone({ params: request.params.set('workspace', mode) }) : request;
  return next(scoped).pipe(map((event) => event instanceof HttpResponse && request.url.startsWith('/api/')
    ? event.clone({ body: workspace.links(event.body, mode) }) : event));
};
