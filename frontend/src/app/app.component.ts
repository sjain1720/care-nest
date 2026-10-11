import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { KeyValuePipe } from '@angular/common';

interface Check {
  ok: boolean;
  detail?: unknown;
  error?: string;
}

interface DiagResponse {
  all_ok: boolean;
  checks: Record<string, Check>;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [KeyValuePipe],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  private http = inject(HttpClient);

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
