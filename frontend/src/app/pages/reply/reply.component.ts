import { TimelineEvent } from '../../models/models';
import { DocumentTasksComponent } from '../../shared/document-tasks.component';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { ApiService, isLive } from '../../services/api.service';
import { DiaryActionsService } from '../../services/diary-actions.service';
import { JourneyService } from '../../services/journey.service';
import { ReplyOutcome, TimelineEventInput } from '../../models/models';
import { InrPipe, formatInr } from '../../shared/inr.pipe';
import { GlossComponent } from '../../shared/gloss.component';
import { NextStep, NextStepsComponent } from '../../shared/next-steps.component';
import { OUTCOME_META, REPLY_DAYS, todayIso } from '../../shared/claim-diary';

/** The insurer answered the family's letter: paste or upload it, see what it means and what to do next. */
@Component({
  selector: 'app-reply',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatIconModule, InrPipe, GlossComponent, TranslatePipe],
  templateUrl: './reply.component.html',
  styles: `
    textarea { width: 100%; min-height: 180px; padding: 12px; font: inherit; color: var(--cn-ink); background: var(--cn-field);
               border: 1px solid var(--cn-border); border-radius: 10px; resize: vertical; }
    textarea:focus { outline: 2px solid var(--cn-primary); border-color: transparent; }
    .result { border-left: 6px solid var(--cn-border-strong); }
    .result.out-ok { border-left-color: var(--cn-ok); }
    .result.out-warn { border-left-color: var(--cn-warn); }
    .result.out-bad { border-left-color: var(--cn-bad); }
    .result.out-info { border-left-color: var(--cn-primary); }
    .section-label { font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; color: var(--cn-muted); margin: 14px 0 4px; }
    .quote { margin: 0; background: var(--cn-bg); border-left: 3px solid var(--cn-border); border-radius: 8px; padding: 8px 12px; font-style: italic; }
    .amount-now { font-size: 1.1rem; }
    .error { color: var(--cn-bad); margin: 8px 0 0; }
    .earlier { list-style: none; margin: 0; padding: 0; }
    .earlier li { padding: 8px 0; border-top: 1px solid var(--cn-border); }
    .earlier li:first-child { border-top: 0; }
  `,
})
export class ReplyComponent {
  private api = inject(ApiService);
  private diary = inject(DiaryActionsService);
  private destroyRef = inject(DestroyRef);
  readonly journey = inject(JourneyService);
  readonly live = isLive('case');

  readonly text = signal('');
  readonly busy = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly replies = computed(() => this.journey.timeline().filter((e) => e.kind === 'reply').reverse());
  readonly latest = computed<TimelineEvent | null>(() => this.replies()[0] ?? null);
  readonly sentBefore = computed(() => this.journey.timeline().some((e) => e.kind !== 'reply' && e.kind !== 'closed'));
  readonly complained = computed(() => this.journey.timeline().some((e) => e.kind === 'complaint_filed'));
  readonly papersSent = computed(() => {
    const r = this.latest();
    return !!r && this.journey.timeline().some((e) => e.kind === 'letter_sent' && e.date >= r.date && this.journey.timeline().indexOf(e) > this.journey.timeline().indexOf(r));
  });

  readonly nextSteps = computed<NextStep[]>(() => {
    const r = this.latest();
    // Before a reply is read, the page intro already says what to do.
    if (!r) return [];
    const complaint: NextStep = { text: "Make a complaint to the insurer's complaints team. We write it for you.", action: 'Make a complaint', route: '/case/letter', query: { kind: 'grievance' }, done: this.complained() };
    const closeIt: NextStep = { text: 'Happy with it? Close your claim.', action: 'Close the claim', route: '/case', fragment: 'diary', done: this.journey.closed() };
    switch (r.outcome) {
      case 'paid_more':
        return [
          { text: `Check that ${r.newApprovedAmount ? formatInr(r.newApprovedAmount) : 'the extra money'} reaches your bank. It can take a few days.` },
          closeIt,
          { text: 'Money not received in a few weeks? Write to them again.', action: 'Write to the insurer', route: '/case/letter', query: { kind: 'grievance' } },
        ];
      case 'explained':
        return [
          { text: 'Read their reason below. Check it against your policy.', action: 'My policy', route: '/policy' },
          closeIt,
          { ...complaint, text: 'Still disagree? Make a complaint to their complaints team.' },
          { text: 'Not sure if their reason is fair? Ask us.', action: 'Ask', ask: "Is the insurer's reason for my deductions fair?" },
        ];
      case 'asks_for_papers':
        return [
          { text: 'Collect the papers they asked for, listed below.', action: 'Papers checklist', route: '/case', fragment: 'checklist' },
          { text: `Send them with a short note. Quote ${r.reference ? 'reference ' + r.reference : 'their reference number'}.` },
          { text: 'Then tap "I\'ve sent the papers", so we count the days.', done: this.papersSent() },
        ];
      case 'no_change':
      case 'rejected':
        return [
          complaint,
          { text: `No answer in ${REPLY_DAYS} days, or still unhappy? Complain on Bima Bharosa, the regulator's site.`, action: 'See steps', route: '/case/letter', query: { kind: 'grievance' }, fragment: 'escalation' },
          { text: 'Still not solved? The Insurance Ombudsman is free. Check its time limit first.', action: 'See steps', route: '/case/letter', query: { kind: 'grievance' }, fragment: 'escalation' },
        ];
      default:
        return [
          { text: 'Read their words below.' },
          { text: 'Ask us what it means for your claim.', action: 'Ask', ask: "What does the insurer's reply mean for my claim?" },
          { text: 'Still unclear? Write and ask for a clear decision.', action: 'Write to the insurer', route: '/case/letter', query: { kind: 'grievance' } },
        ];
    }
  });

  constructor() {
    if (!this.live) {
      this.api.getSampleReply().pipe(takeUntilDestroyed()).subscribe((t) => {
        if (!this.text()) this.text.set(t);
      });
    }
  }

  meta(outcome: ReplyOutcome | undefined) {
    return OUTCOME_META[outcome ?? 'unclear'];
  }

  read(): void {
    const text = this.text().trim();
    if (text.length < 20 || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.submitReply(text).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.busy.set(false);
        this.text.set('');
        setTimeout(() => document.getElementById('result')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      },
      error: (e) => {
        this.busy.set(false);
        this.error.set(e?.error?.detail ?? "We couldn't read the reply. Please try again.");
      },
    });
  }

  close(): void {
    this.add({ kind: 'closed', date: todayIso() });
  }

  markPapersSent(): void {
    this.add({ kind: 'letter_sent', date: todayIso(), note: 'Sent the papers the insurer asked for' });
  }

  remove(id: string): void {
    this.api.removeTimelineEvent(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  private add(input: TimelineEventInput): void {
    this.saving.set(true);
    this.diary.add(input).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => this.saving.set(false),
      error: () => this.saving.set(false),
    });
  }
}
