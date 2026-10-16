import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { tap } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { DiaryActionsService } from '../../services/diary-actions.service';
import { JourneyService } from '../../services/journey.service';
import { ChecklistItem, ChecklistStatus, TimelineEvent } from '../../models/models';
import { NextStep, NextStepsComponent } from '../../shared/next-steps.component';
import { EmptyStateComponent, SkeletonComponent } from '../../shared/page-states.component';
import { eventText, todayIso } from '../../shared/claim-diary';
import { ClaimsListComponent } from './claims-list.component';
import { DocumentPreviewComponent } from '../../shared/document-preview.component';
import { CoverageEstimateComponent } from '../../shared/coverage-estimate.component';
import { InrPipe } from '../../shared/inr.pipe';

const STATUS_META: Record<ChecklistStatus, { label: string; icon: string; tone: string }> = {
  collected: { label: 'Have it', icon: 'check_circle', tone: 'ok' },
  missing: { label: 'Still needed', icon: 'radio_button_unchecked', tone: 'warn' },
  requested: { label: 'Asked for', icon: 'schedule', tone: 'info' },
};

@Component({
  selector: 'app-case',
  standalone: true,
  imports: [DocumentPreviewComponent, CoverageEstimateComponent, DatePipe, NgTemplateOutlet, FormsModule, RouterLink, MatButtonModule, MatIconModule, MatProgressBarModule, NextStepsComponent, SkeletonComponent, EmptyStateComponent, ClaimsListComponent, TranslatePipe, InrPipe],
  templateUrl: './case.component.html',
  styleUrl: './case-overview.css',
  styles: `
    .head-row { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px 16px; }
    .head-text { min-width: 0; }
    .head-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .facts { display: grid; gap: 8px 16px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); font-size: .9rem; }
    .facts div span { display: block; color: var(--cn-muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; }
    .check { display: flex; gap: 12px; align-items: flex-start; padding: 12px 0; border-top: 1px solid var(--cn-border); }
    .check:first-of-type { border-top: 0; }
    .check .body { flex: 1; min-width: 0; }
    .check .name-row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; margin-bottom: 2px; }
    .check .name { font-weight: 600; }
    .check .meta { font-size: .85rem; color: var(--cn-muted); }
    .toggle { flex: none; }
    .docs { list-style: none; margin: 0; padding: 0; }
    .docs li { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--cn-border); }
    .docs li:first-child { border-top: 0; }
    .docs mat-icon { color: var(--cn-pdf); }
    mat-progress-bar { margin: 8px 0 4px; border-radius: 999px; }
    .asked { min-height: 36px; margin-top: 4px; }
    .diary { list-style: none; margin: 8px 0 0; padding: 0; }
    .diary li { display: flex; align-items: center; gap: 4px 12px; padding: 6px 0; border-top: 1px solid var(--cn-border); font-size: .9rem; }
    .diary li:first-child { border-top: 0; }
    .diary .d-date { flex: none; width: 92px; color: var(--cn-muted); font-size: .8rem; }
    .diary .d-text { flex: 1; min-width: 0; }
    .mark { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px 12px; margin-top: 12px; }
    .mark label { display: flex; flex-direction: column; gap: 4px; font-size: .85rem; color: var(--cn-muted); }
    .mark input { min-height: 44px; padding: 0 10px; font: inherit; color: var(--cn-ink); border: 1px solid var(--cn-border); border-radius: 10px; background: var(--cn-field); }
    .wait { border-radius: 10px; padding: 8px 12px; margin-top: 12px; font-size: .9rem; }
    .start-card { display: flex; gap: 16px; align-items: flex-start; border-color: var(--cn-c1-line);
                  background: linear-gradient(135deg, var(--cn-c1-soft), var(--cn-surface) 70%); }
    .sc-icon { flex: none; width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; background: var(--cn-c1-soft); color: var(--cn-c1-ink); }
    .sc-text h2 { margin: 0 0 4px; }
    .sc-text p { margin: 0 0 12px; }
    @media (max-width: 599px) { .start-card { flex-direction: column; } }
  `,
})
export class CaseComponent {
  readonly dashboard = inject(ActivatedRoute).snapshot.data['dashboard'] === true;
  private api = inject(ApiService);
  readonly workspace = this.api.workspace;
  readonly claims = toSignal(this.api.getClaims());
  readonly policy = toSignal(this.api.getPolicy());
  private diary = inject(DiaryActionsService);
  readonly journey = inject(JourneyService);

  /** Local, editable copy of the checklist (saved by the backend, or in this browser in demo mode). */
  checklist = signal<ChecklistItem[]>([]);
  claimCase = toSignal(this.api.getCase().pipe(tap((c) => this.checklist.set((c?.checklist ?? []).map((i) => ({ ...i }))))));

  readonly decisionDocument = computed(() => this.claimCase()?.documents.find(d => d.type === 'Settlement letter' || d.type === 'Rejection letter'));

  claimItems = computed(() => this.checklist().filter((i) => i.group === 'claim'));
  disputeItems = computed(() => this.checklist().filter((i) => i.group === 'dispute'));
  collected = computed(() => this.claimItems().filter((i) => i.status === 'collected').length);
  progressPct = computed(() => (this.claimItems().length ? (this.collected() / this.claimItems().length) * 100 : 0));
  readonly bill = toSignal(this.api.getBill());
  readonly settlement = toSignal(this.api.getSettlement());
  readonly tools = [
    { label: 'Check my bill', icon: 'receipt_long', route: '/case/bill', fragment: undefined },
    { label: 'Why money was cut', icon: 'stacked_bar_chart', route: '/case/settlement', fragment: undefined },
    { label: 'Write to the insurer', icon: 'edit_note', route: '/case/letter', fragment: undefined },
    { label: "Insurer's reply", icon: 'mark_email_read', route: '/case/reply', fragment: undefined },
    { label: "Insurer's question", icon: 'quiz', route: '/case/query', fragment: undefined },
    { label: 'Papers checklist', icon: 'checklist', route: '/case', fragment: 'checklist' },
    { label: 'Claim diary', icon: 'history_edu', route: '/case', fragment: 'diary' },
    { label: 'Add documents', icon: 'upload_file', route: '/upload', fragment: undefined },
  ];
  /** Nothing uploaded, ticked off in the diary or read from a bill yet: show how to start instead of empty sections. */
  readonly isEmpty = computed(() => {
    const c = this.claimCase();
    return !!c && !c.documents.length && !c.timeline?.length && !this.bill();
  });

  readonly timeline = this.journey.timeline;
  readonly sentClaim = computed(() => this.timeline().some((e) => e.kind === 'claim_sent'));
  readonly diaryDate = signal(todayIso());
  readonly today = todayIso();
  readonly saving = signal(false);

  nextSteps = computed<NextStep[]>(() => {
    if (!this.claimCase()) return [];
    const steps: NextStep[] = [];
    const n = this.journey.nextAction();
    if (n) steps.push({ text: `${n.title}. ${n.text}`, action: n.action, route: n.route, fragment: n.fragment, query: n.query });
    const missing = this.claimItems().filter((i) => i.status === 'missing');
    if (missing.length) {
      const names = missing.slice(0, 3).map((i) => i.name.toLowerCase()).join(', ');
      steps.push({ text: `Collect ${missing.length} more paper${missing.length === 1 ? '' : 's'}: ${names}${missing.length > 3 ? '…' : ''}.`, action: 'Papers checklist', route: '/case', fragment: 'checklist' });
    } else if (this.claimItems().length) {
      steps.push({ text: 'You have every paper for the claim.', done: true });
    }
    if (!this.bill()) steps.push({ text: 'Add your final hospital bill so we can check it.', action: 'Add the hospital bill', route: '/upload', query: { type: 'Hospital bill' } });
    return steps;
  });

  status(s: ChecklistStatus) {
    return STATUS_META[s];
  }

  text(e: TimelineEvent): string {
    return eventText(e);
  }

  toggle(id: string): void {
    const item = this.checklist().find((i) => i.id === id);
    if (item) this.setStatus(item, item.status === 'collected' ? 'missing' : 'collected');
  }

  askedFor(id: string): void {
    const item = this.checklist().find((i) => i.id === id);
    if (item) this.setStatus(item, 'requested');
  }

  private setStatus(item: ChecklistItem, status: ChecklistStatus): void {
    this.checklist.update((list) => list.map((i): ChecklistItem => (i.id === item.id ? { ...i, status } : i)));
    this.api.updateChecklistItem(item.id, status).subscribe({
      error: () => this.checklist.update((list) => list.map((i): ChecklistItem => (i.id === item.id ? item : i))),
    });
  }

  add(kind: 'claim_sent' | 'closed'): void {
    if (!this.diaryDate()) return;
    this.saving.set(true);
    this.diary.add({ kind, date: this.diaryDate() }).subscribe({ next: () => this.saving.set(false), error: () => this.saving.set(false) });
  }

  remove(id: string): void {
    this.api.removeTimelineEvent(id).subscribe();
  }

  reopen(): void {
    const closed = [...this.timeline()].reverse().find((e) => e.kind === 'closed');
    if (closed) this.remove(closed.id);
  }
}
