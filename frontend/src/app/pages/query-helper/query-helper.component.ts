import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { AgentStep, QueryHelp } from '../../models/models';
import { AgentProgressComponent } from '../../shared/agent-progress.component';
import { CitationChipComponent } from '../../shared/citation-chip.component';

/** In hospital, cashless: turns an insurer/TPA query into plain words, a document list and a reply. */
@Component({
  selector: 'app-query-helper',
  standalone: true,
  imports: [FormsModule, RouterLink, MatButtonModule, MatIconModule, AgentProgressComponent, CitationChipComponent],
  templateUrl: './query-helper.component.html',
  styles: `
    textarea { width: 100%; min-height: 140px; padding: 12px; font: inherit; border: 1px solid var(--cn-border); border-radius: 10px; resize: vertical; }
    textarea:focus { outline: 2px solid var(--cn-primary); border-color: transparent; }
    .urgent { display: flex; gap: 8px; align-items: flex-start; background: var(--cn-warn-soft); color: var(--cn-warn); border-radius: 10px; padding: 10px 12px; font-weight: 600; }
    .doc { display: flex; gap: 12px; padding: 10px 0; border-top: 1px solid var(--cn-border); }
    .doc:first-of-type { border-top: 0; }
    .doc .num { flex: none; width: 28px; height: 28px; border-radius: 50%; background: var(--cn-primary-soft); color: var(--cn-primary);
                font-weight: 700; display: flex; align-items: center; justify-content: center; }
    .doc .meta { font-size: .85rem; color: var(--cn-muted); }
    pre { white-space: pre-wrap; font: inherit; background: var(--cn-bg); border-radius: 10px; padding: 12px; margin: 0 0 12px; }
  `,
})
export class QueryHelperComponent {
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);

  queryText = '';
  steps = signal<AgentStep[]>([]);
  help = signal<QueryHelp | null>(null);
  busy = signal(false);
  copied = signal(false);

  constructor() {
    this.api.getSampleQuery().pipe(takeUntilDestroyed(this.destroyRef)).subscribe((q) => (this.queryText = q));
  }

  explain(): void {
    if (!this.queryText.trim() || this.busy()) return;
    this.busy.set(true);
    this.steps.set([]);
    this.help.set(null);
    this.api.explainQuery(this.queryText).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (e) => (e.type === 'step' ? this.steps.update((s) => [...s, e.step]) : this.help.set(e.help)),
      error: () => this.busy.set(false),
      complete: () => this.busy.set(false),
    });
  }

  async copyReply(): Promise<void> {
    const h = this.help();
    if (!h) return;
    await navigator.clipboard.writeText(h.draftReply);
    this.copied.set(true);
    setTimeout(() => this.copied.set(false), 2000);
  }
}
