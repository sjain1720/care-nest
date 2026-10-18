import { DocumentPreviewComponent } from '../../shared/document-preview.component';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { JourneyService } from '../../services/journey.service';
import { OUTCOME_META } from '../../shared/claim-diary';
import { InrPipe, formatInr } from '../../shared/inr.pipe';
import { NextStep, NextStepsComponent } from '../../shared/next-steps.component';
import { EmptyStateComponent, SkeletonComponent } from '../../shared/page-states.component';
import { GlossComponent } from '../../shared/gloss.component';
import { CitationChipComponent } from '../../shared/citation-chip.component';
import { TrustPillComponent } from '../../shared/trust-pill.component';
import { WaterfallComponent, WaterfallStep } from '../../shared/waterfall.component';
import { DisputeReviewComponent } from '../../shared/dispute-review.component';
import { plainCutName } from '../../shared/plain-words';

const SEGMENT_COLORS = ['var(--cn-seg-1)', 'var(--cn-seg-2)', 'var(--cn-seg-3)', 'var(--cn-seg-4)', 'var(--cn-seg-5)'];

@Component({
  selector: 'app-settlement',
  standalone: true,
  imports: [DocumentPreviewComponent, DatePipe, RouterLink, MatButtonModule, MatIconModule, InrPipe, CitationChipComponent, TrustPillComponent, WaterfallComponent, TranslatePipe,
            SkeletonComponent, EmptyStateComponent, GlossComponent, DisputeReviewComponent],
  templateUrl: './settlement.component.html',
  styles: `
    .totals { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .totals .value { font-size: 1.4rem; }
    .totals .deducted .value { color: var(--cn-bad); }
    @media (max-width: 599px) { .totals { grid-template-columns: 1fr; } }
    .math { margin-top: 12px; }
    .deduction { border-left: 6px solid; }
    .deduction .insurer-name { display: block; font-size: .75rem; font-weight: 400; color: var(--cn-muted); }
    /* Wide screens: summary and steps on the left, each cut on the right. */
    .split-layout { display: block; }
    @media (min-width: 1200px) {
      .split-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); gap: 16px; align-items: start; }
      .split-layout .left { position: sticky; top: calc(var(--cn-topbar-h) + 12px); }
    }
    .deduction summary { list-style: none; cursor: pointer; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .deduction summary::-webkit-details-marker { display: none; }
    .deduction .title { font-weight: 600; flex: 1; min-width: 180px; }
    .deduction .amount { font-size: 1.15rem; }
    .section-label { font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; color: var(--cn-muted); margin: 14px 0 4px; }
    .insurer { background: var(--cn-bg); border-left: 3px solid var(--cn-border); border-radius: 8px; padding: 8px 12px; font-style: italic; }
    ul.plain { margin: 4px 0; padding-left: 20px; }
    .questions li { margin-bottom: 4px; }
    .reply-banner { display: flex; align-items: center; gap: 12px; text-decoration: none; color: inherit; border-left: 4px solid var(--cn-primary); }
    .reply-banner .grow { flex: 1; min-width: 0; }
  `,
})
export class SettlementComponent {
  private api = inject(ApiService);
  private params = toSignal(inject(ActivatedRoute).queryParamMap);
  readonly decisionOnly = computed(() => this.params()?.get('step') === 'decision');
  readonly claimCase = toSignal(this.api.getCase());
  readonly original = computed(() => this.claimCase()?.documents.find(d => d.type === 'Settlement letter' || d.type === 'Rejection letter'));
  readonly journey = inject(JourneyService);
  readonly rejection = this.journey.rejection;
  preparation = toSignal(this.api.getDisputePreparation());
  settlement = toSignal(this.api.getSettlement());
  bill = toSignal(this.api.getBill());
  /** undefined = nothing chosen yet, so the deduction in the link (#d3) or the first unexplained one is opened. */
  private chosen = signal<string | null | undefined>(undefined);
  open = computed(() => {
    const ds = this.settlement()?.deductions ?? [];
    const chosen = this.chosen();
    if (chosen === null || ds.some((d) => d.id === chosen)) return chosen ?? null;
    return (ds.find((d) => d.trust === 'unknown') ?? ds[0])?.id ?? null;
  });

  constructor() {
    inject(ActivatedRoute).fragment.pipe(takeUntilDestroyed()).subscribe((f) => f && this.chosen.set(f));
  }

  totalDeducted = computed(() => this.settlement()?.deductions.reduce((s, d) => s + d.amount, 0) ?? 0);
  waterfallSteps = computed<WaterfallStep[]>(() =>
    (this.settlement()?.deductions ?? []).map((d, i) => ({ id: d.id, label: this.plain(d), insurerLabel: d.label, amount: d.amount, color: this.color(i) })));
  explained = computed(() => this.settlement()?.deductions.filter((d) => d.trust !== 'unknown').reduce((s, d) => s + d.amount, 0) ?? 0);
  arithmeticOk = computed(() => {
    const s = this.settlement();
    return !!s && s.claimedAmount !== null && s.approvedAmount !== null && s.claimedAmount - this.totalDeducted() === s.approvedAmount;
  });

  nextSteps = computed<NextStep[]>(() => {
    const s = this.settlement();
    if (!s) return [];
    const letter = { kind: 'clarification' };
    const sent = this.journey.lettersSent().length > 0;
    const reply = this.journey.lastReply();
    const steps: NextStep[] = [];
    if (reply) {
      steps.push({ text: `The insurer replied: ${OUTCOME_META[reply.outcome ?? 'unclear'].label.toLowerCase()}.`, action: 'See the reply', route: '/case/reply' });
    }
    if (this.totalDeducted() === 0) {
      steps.push({ text: 'No itemized deductions are recorded. Check the approved amount and confirm payment separately.', done: true });
      steps.push({ text: 'Check the money reached your bank.' });
      steps.push({ text: 'Then close your claim.', action: 'Close the claim', route: '/case', fragment: 'diary', done: this.journey.closed() });
      return steps;
    }
    const unexplained = this.totalDeducted() - this.explained();
    if (!this.arithmeticOk()) {
      steps.push({ text: "The insurer's numbers don't add up. Ask them for a corrected letter.", action: 'Write to the insurer', route: '/case/letter', query: letter, done: sent });
    }
    if (unexplained > 0) {
      steps.push({ text: `Ask the insurer why ${formatInr(unexplained)} was cut with no clear reason.`, action: 'Write to the insurer', route: '/case/letter', query: letter, done: sent });
    }
    if (s.deductions.some((d) => /room/i.test(d.label))) {
      steps.push({ text: 'Was no cheaper room free when you were admitted? Get a note from the hospital saying so.', action: 'Extra papers', route: '/case', fragment: 'dispute-papers' });
    }
    steps.push({ text: 'Send the letter with the papers it lists. Then mark it as sent, so we count the days.', action: 'Mark as sent', route: '/case/letter', query: letter, fragment: 'sent', done: sent });
    if (sent && !reply) steps.push({ text: 'When the insurer answers, add their reply.', action: 'They replied', route: '/case/reply' });
    steps.push({ text: 'Not sure which cut to question? Ask us.', action: 'Ask', ask: 'Which deduction can I challenge?' });
    return steps;
  });

  readonly refusalSteps = computed<NextStep[]>(() => {
    const asked = this.journey.timeline().some((e) => e.kind === 'letter_sent' && e.letterKind === 'reconsideration');
    return [
      { text: 'Ask us what their reason means for you.', action: 'Ask', ask: 'Why was my claim refused?' },
      { text: 'Get a letter from your doctor explaining the treatment.', action: 'Extra papers', route: '/case', fragment: 'dispute-papers' },
      { text: 'Ask them to look again. We write the letter; you send it and mark it as sent.', action: 'Write to the insurer', route: '/case/letter', query: { kind: 'reconsideration' }, done: asked },
      { text: 'No answer, or still refused? Complain to the next level.', action: 'See steps', route: '/case/letter', query: { kind: 'grievance' }, fragment: 'escalation' },
    ];
  });

  outcomeLabel(outcome: string | undefined): string {
    return OUTCOME_META[(outcome ?? 'unclear') as keyof typeof OUTCOME_META]?.label ?? OUTCOME_META.unclear.label;
  }

  color(index: number): string {
    return SEGMENT_COLORS[index % SEGMENT_COLORS.length];
  }

  plain(d: { label: string; insurerReason: string }): string {
    return plainCutName(d.label, d.insurerReason);
  }

  select(id: string): void {
    this.chosen.set(id);
    setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }

  onToggle(id: string, event: Event): void {
    const isOpen = (event.target as HTMLDetailsElement).open;
    if (isOpen) this.chosen.set(id);
    else if (this.open() === id) this.chosen.set(null);
  }
}
