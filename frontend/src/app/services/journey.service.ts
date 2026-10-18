import { Injectable, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ApiService } from './api.service';
import { ClaimDocuments, LetterKind, TimelineEvent } from '../models/models';
import { DECISION_DAYS, REPLY_DAYS, daysSince, sortedTimeline, suggestLetter } from '../shared/claim-diary';

import { claimJourney } from '../shared/claim-flow';
/** The one thing to do next, shown on the dashboard and the claim page. */
export interface NextAction {
  tone: 'bad' | 'warn' | 'info' | 'ok';
  icon: string;
  title: string;
  text: string;
  action: string;
  route: string;
  fragment?: string;
  query?: Record<string, string>;
}

const SENT_KINDS = ['claim_sent', 'letter_sent', 'complaint_filed', 'query_answered'];

/** Where the user is in their claim, from upload to closing it. */
@Injectable({ providedIn: 'root' })
export class JourneyService {
  private api = inject(ApiService);
  private policy = toSignal(this.api.getPolicy());
  readonly claimCase = toSignal(this.api.getCase());
  private bill = toSignal(this.api.getBill());
  private settlement = toSignal(this.api.getSettlement());

  readonly timeline = computed(() => sortedTimeline(this.claimCase()?.timeline));
  private latestOf(kinds: string[]): TimelineEvent | null {
    return [...this.timeline()].reverse().find((e) => kinds.includes(e.kind)) ?? null;
  }
  readonly lastReply = computed(() => this.latestOf(['reply']));
  readonly lastSent = computed(() => this.latestOf(this.decided() ? SENT_KINDS.filter((k) => k !== 'query_answered') : SENT_KINDS));
  readonly closed = computed(() => this.timeline().filter(e => e.kind !== 'outcome_recorded' && e.kind !== 'payment_recorded').at(-1)?.kind === 'closed');
  readonly rejection = computed(() => this.claimCase()?.rejection ?? null);
  readonly decided = computed(() => this.claimCase()?.financials?.decisionAvailable ?? (!!this.settlement() || !!this.rejection()));
  readonly cutTotal = computed(() => this.settlement()?.deductions.reduce((s, d) => s + d.amount, 0) ?? 0);
  /** Full amount approved with no recorded deductions: follow-up may be unnecessary. */
  readonly nothingToQuestion = computed(() => !!this.settlement() && !this.rejection() && this.cutTotal() === 0 && this.settlement()!.claimedAmount !== null && this.settlement()!.approvedAmount !== null && this.settlement()!.claimedAmount === this.settlement()!.approvedAmount);
  readonly lettersSent = computed(() => this.timeline().filter((e) => e.kind === 'letter_sent' || e.kind === 'complaint_filed'));
  readonly suggestedLetter = computed<LetterKind>(() => suggestLetter(this.claimCase(), this.settlement()));

  /** The last thing sent, if the insurer hasn't replied since. */
  readonly awaiting = computed<TimelineEvent | null>(() => {
    const sent = this.lastSent();
    const reply = this.lastReply();
    if (!sent || this.closed()) return null;
    if (reply && this.timeline().indexOf(reply) > this.timeline().indexOf(sent)) return null;
    if (sent.kind === 'claim_sent' && this.decided()) return null;
    return sent;
  });
  readonly waitingDays = computed(() => {
    const a = this.awaiting();
    return a ? daysSince(a.date) : 0;
  });
  readonly overdue = computed(() => {
    const a = this.awaiting();
    if (!a || (a.kind === 'complaint_filed' && (a.level ?? 1) >= 2) || a.kind === 'query_answered') return false;
    return this.waitingDays() > (a.kind === 'claim_sent' ? DECISION_DAYS : REPLY_DAYS);
  });

  private requestedReview = signal<{workspace:string;replyId:string;fingerprint:string;ready:boolean}|null>(null);
  recordDocumentReview(data: ClaimDocuments): void {
    if (!data.replyId) return;
    const tasks = data.tasks.filter(t => t.kind === 'reply');
    this.requestedReview.set({workspace:this.api.workspaceKey(),replyId:data.replyId,fingerprint:data.fingerprint,
      ready:tasks.length > 0 && tasks.every(t => t.reviewed || t.notApplicable)});
  }
  private requestedReady = computed(() => this.requestedReview()?.workspace === this.api.workspaceKey() && this.requestedReview()?.replyId === this.lastReply()?.id && this.requestedReview()?.ready === true);
  readonly draftReady = signal(false);
  private responseReview = signal('');
  private reviewScope = computed(() => JSON.stringify({workspace:this.api.workspaceKey(),
    claim:this.claimCase()?.id, documents:this.claimCase()?.documents, policy:this.policy(),
    bill:this.bill(), decision:this.settlement(), rejection:this.rejection(), reply:this.lastReply(), tasks:this.requestedReview()}));
  readonly responseReviewed = computed(() => this.responseReview() === this.reviewScope());
  markResponseReviewed(): void { this.responseReview.set(this.reviewScope()); }
  clearResponseReview(): void { this.responseReview.set(''); }
  readonly flow = computed(() => claimJourney(this.claimCase(),this.bill(),!!this.policy(),this.decided(),this.nothingToQuestion(),this.responseReviewed(),this.requestedReady()));
  readonly steps = computed(() => this.flow().steps);
  readonly currentIndex = computed(() => this.flow().currentIndex);
  readonly current = computed<import('../shared/claim-flow').JourneyStep | null>(() => this.steps()[this.currentIndex()] ?? null);
  readonly doneCount = computed(() => this.steps().filter((s) => s.done).length);

  readonly nextAction = computed<NextAction | null>(() => {
    if (!this.claimCase()) return null;
    const step = this.current() ?? this.steps()[8];
    return {tone:this.closed() ? 'ok' : 'info',icon:this.closed() ? 'task_alt' : 'arrow_forward',
      title:this.closed() ? 'This claim is closed' : step.label,text:this.flow().note,
      action:this.closed() ? 'Review outcome' : step.label,route:step.route,query:step.query,fragment:step.fragment};
  });
}
