import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { KeyValuePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { ApiService, FEATURES, Feature, isLive, saveLiveFeatures, setAllLive } from '../../services/api.service';

interface Check {
  ok: boolean;
  detail?: unknown;
  error?: string;
}

interface DiagResponse {
  all_ok: boolean;
  checks: Record<string, Check>;
}

/** Demo and live settings: which features use the live backend, its health, and a developer check of every Google service (/api/diag). */
@Component({
  selector: 'app-status',
  standalone: true,
  imports: [KeyValuePipe, MatButtonModule, TranslatePipe],
  templateUrl: './status.component.html',
  styles: `
    .checks { list-style: none; padding: 0; margin: 16px 0 0; }
    .checks li { padding: 8px 0; border-top: 1px solid var(--cn-border); }
    .detail { display: block; color: var(--cn-muted); font-size: .9rem; margin-top: 4px; word-break: break-word; }
    .error { color: var(--cn-bad); }
    .feature { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--cn-border); }
    .feature input { width: 20px; height: 20px; }
    .feature.disabled { color: var(--cn-muted); }
    .dev summary { cursor: pointer; min-height: 40px; display: flex; align-items: center; color: var(--cn-link); font-weight: 600; }
    .dev button { margin-top: 8px; }
    .quick { gap: 8px; margin-bottom: 4px; }
  `,
})
export class StatusComponent {
  private http = inject(HttpClient);
  private api = inject(ApiService);
  demoLoading = signal(false);
  actionError = signal<string | null>(null);
  deleting = signal(false);
  loadLiveDemo(): void {
    this.demoLoading.set(true);
    this.actionError.set(null);
    this.api.loadDemoCase().subscribe({
      next: () => { setAllLive(true); location.assign('/'); },
      error: (e) => { this.demoLoading.set(false); this.actionError.set(e?.error?.detail || 'Live demo failed. Please retry.'); },
    });
  }
  deleteGuestData(): void {
    this.deleting.set(true);
    this.actionError.set(null);
    this.http.delete('/api/session').subscribe({
      next: () => { setAllLive(true); location.assign('/'); },
      error: () => { this.deleting.set(false); this.actionError.set('Deletion failed. Please retry.'); },
    });
  }

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

  useAll(on: boolean): void {
    setAllLive(on);
    location.reload();
  }

  health = signal<string>('checking');
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
