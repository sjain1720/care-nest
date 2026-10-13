import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { DiaryActionsService } from '../../services/diary-actions.service';
import { JourneyService } from '../../services/journey.service';
import { AgentStep, QueryHelp } from '../../models/models';
import { todayIso } from '../../shared/claim-diary';
import { AgentProgressComponent } from '../../shared/agent-progress.component';
import { CitationChipComponent } from '../../shared/citation-chip.component';
import { NextStep, NextStepsComponent } from '../../shared/next-steps.component';

/** In hospital, cashless: turns an insurer/TPA query into plain words, a document list and a reply. */
@Component({
  selector: 'app-query-helper',
  standalone: true,
  imports: [FormsModule, RouterLink, MatButtonModule, MatIconModule, AgentProgressComponent, CitationChipComponent, NextStepsComponent, TranslatePipe],
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
  private journey = inject(JourneyService);
  private diary = inject(DiaryActionsService);
  /** Answered today, so the button doesn't add the same entry twice. */
  readonly answered = computed(() => this.journey.timeline().find((e) => e.kind === 'query_answered' && e.date === todayIso()) ?? null);
  readonly saving = signal(false);

  queryText = '';
  steps = signal<AgentStep[]>([]);
  help = signal<QueryHelp | null>(null);
  busy = signal(false);
  copied = signal(false);
  nextSteps = computed<NextStep[]>(() => {
    const h = this.help();
    // Before the message is explained, the page intro already says what to do.
    if (!h) return [];
    return [
      { text: "Read what the message means, below. It is a pause, not a no.", done: true },
      { text: `Collect the ${h.documents.length} paper${h.documents.length === 1 ? '' : 's'} listed below.` },
      { text: "Give them, with our reply, to the hospital's insurance desk today." },
      { text: 'Then tap "I\'ve handed it in", so it goes in your claim diary with the date.', done: !!this.answered() },
    ];
  });

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

  markAnswered(): void {
    this.saving.set(true);
    this.diary.add({ kind: 'query_answered', date: todayIso(), note: this.help()?.queryType }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => this.saving.set(false),
      error: () => this.saving.set(false),
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
