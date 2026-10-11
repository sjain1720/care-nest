import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { tap } from 'rxjs';
import { ApiService } from '../../services/api.service';
import { ChecklistItem, ChecklistStatus } from '../../models/models';

const STATUS_META: Record<ChecklistStatus, { label: string; icon: string; tone: string }> = {
  collected: { label: 'Collected', icon: 'check_circle', tone: 'ok' },
  missing: { label: 'Missing', icon: 'radio_button_unchecked', tone: 'warn' },
  requested: { label: 'Requested', icon: 'schedule', tone: 'info' },
};

@Component({
  selector: 'app-case',
  standalone: true,
  imports: [DatePipe, NgTemplateOutlet, RouterLink, MatButtonModule, MatIconModule, MatProgressBarModule],
  templateUrl: './case.component.html',
  styles: `
    .facts { display: grid; gap: 8px 16px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); font-size: .9rem; }
    .facts div span { display: block; color: var(--cn-muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .check { display: flex; gap: 12px; align-items: flex-start; padding: 12px 0; border-top: 1px solid var(--cn-border); }
    .check:first-of-type { border-top: 0; }
    .check .body { flex: 1; }
    .check .name { font-weight: 600; }
    .check .meta { font-size: .85rem; color: var(--cn-muted); }
    .toggle { flex: none; }
    .docs { list-style: none; margin: 0; padding: 0; }
    .docs li { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--cn-border); }
    .docs li:first-child { border-top: 0; }
    .docs mat-icon { color: #c5221f; }
    mat-progress-bar { margin: 8px 0 4px; border-radius: 999px; }
  `,
})
export class CaseComponent {
  private api = inject(ApiService);

  /** Local, editable copy of the checklist (persisted by the backend later). */
  checklist = signal<ChecklistItem[]>([]);
  claimCase = toSignal(this.api.getCase().pipe(tap((c) => this.checklist.set((c?.checklist ?? []).map((i) => ({ ...i }))))));

  claimItems = computed(() => this.checklist().filter((i) => i.group === 'claim'));
  disputeItems = computed(() => this.checklist().filter((i) => i.group === 'dispute'));
  collected = computed(() => this.claimItems().filter((i) => i.status === 'collected').length);
  progressPct = computed(() => (this.claimItems().length ? (this.collected() / this.claimItems().length) * 100 : 0));

  status(s: ChecklistStatus) {
    return STATUS_META[s];
  }

  toggle(id: string): void {
    const item = this.checklist().find((i) => i.id === id);
    if (!item) return;
    const status: ChecklistStatus = item.status === 'collected' ? 'missing' : 'collected';
    this.checklist.update((list) => list.map((i): ChecklistItem => (i.id === id ? { ...i, status } : i)));
    this.api.updateChecklistItem(id, status).subscribe({
      error: () => this.checklist.update((list) => list.map((i): ChecklistItem => (i.id === id ? item : i))),
    });
  }
}
