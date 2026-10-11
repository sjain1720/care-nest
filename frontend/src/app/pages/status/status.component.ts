import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { KeyValuePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { FEATURES, Feature, isLive, saveLiveFeatures } from '../../services/api.service';

interface Check {
  ok: boolean;
  detail?: unknown;
  error?: string;
}

interface DiagResponse {
  all_ok: boolean;
  checks: Record<string, Check>;
}

/** Developer page: backend health and a one-click check of every Google service (/api/diag). */
@Component({
  selector: 'app-status',
  standalone: true,
  imports: [KeyValuePipe, MatButtonModule],
  templateUrl: './status.component.html',
  styles: `
    .checks { list-style: none; padding: 0; margin: 16px 0 0; }
    .checks li { padding: 8px 0; border-top: 1px solid var(--cn-border); }
    .detail { display: block; color: var(--cn-muted); font-size: .9rem; margin-top: 4px; word-break: break-word; }
    .error { color: var(--cn-bad); }
    .feature { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--cn-border); }
    .feature input { width: 20px; height: 20px; }
    .feature.disabled { color: var(--cn-muted); }
  `,
})
export class StatusComponent {
  private http = inject(HttpClient);

  readonly features = FEATURES;
  live = signal<Set<Feature>>(new Set(FEATURES.filter((f) => isLive(f.id)).map((f) => f.id)));

  toggle(id: Feature, on: boolean): void {
    this.live.update((s) => {
      const next = new Set(s);
      if (on) next.add(id); else next.delete(id);
      return next;
    });
  }

  applyLive(): void {
    saveLiveFeatures([...this.live()]);
    location.reload();
  }

  health = signal<string>('checking…');
  diag = signal<DiagResponse | null>(null);
  diagLoading = signal(false);
  diagError = signal<string | null>(null);

  constructor() {
    this.http.get<{ status: string }>('/api/health').subscribe({
      next: (r) => this.health.set(r.status),
      error: () => this.health.set('unreachable'),
    });
  }

  runDiag(): void {
    this.diagLoading.set(true);
    this.diagError.set(null);
    this.http.get<DiagResponse>('/api/diag').subscribe({
      next: (r) => {
        this.diag.set(r);
        this.diagLoading.set(false);
      },
      error: (e) => {
        this.diagError.set(e?.message ?? 'Request failed');
        this.diagLoading.set(false);
      },
    });
  }
}
