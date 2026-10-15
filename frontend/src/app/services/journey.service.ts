import { Injectable, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ApiService } from './api.service';
import { LetterKind, TimelineEvent } from '../models/models';
import { DECISION_DAYS, REPLY_DAYS, daysSince, shortDate, sortedTimeline, suggestLetter } from '../shared/claim-diary';
import { formatInr } from '../shared/inr.pipe';

export interface JourneyStep {
  label: string;
  /** What to do while this is the current step, e.g. "Wait for their reply". */
  todo: string;
  done: boolean;
  route: string;
  fragment?: string;
  query?: Record<string, string>;
}

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

  private claimItems = computed(() => (this.claimCase()?.checklist ?? []).filter((i) => i.group === 'claim'));
  readonly timeline = computed(() => sortedTimeline(this.claimCase()?.timeline));
  private latestOf(kinds: string[]): TimelineEvent | null {
    return [...this.timeline()].reverse().find((e) => kinds.includes(e.kind)) ?? null;
  }
  readonly lastReply = computed(() => this.latestOf(['reply']));
  readonly lastSent = computed(() => this.latestOf(this.decided() ? SENT_KINDS.filter((k) => k !== 'query_answered') : SENT_KINDS));
  readonly closed = computed(() => this.timeline().at(-1)?.kind === 'closed');
  readonly rejection = computed(() => this.claimCase()?.rejection ?? null);
  readonly decided = computed(() => !!this.settlement() || !!this.rejection());
  readonly cutTotal = computed(() => this.settlement()?.deductions.reduce((s, d) => s + d.amount, 0) ?? 0);
  /** Paid in full and not refused: no letter or reply needed. */
  readonly nothingToQuestion = computed(() => !!this.settlement() && !this.rejection() && this.cutTotal() === 0);
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

  readonly steps = computed<JourneyStep[]>(() => {
    const collected = this.claimItems().length > 0 && this.claimItems().every((i) => i.status === 'collected');
    const sent = this.timeline().some((e) => e.kind === 'claim_sent') || this.decided();
    const skip = this.nothingToQuestion();
    return [
      { label: 'Policy read', todo: 'Add your policy', done: !!this.policy(), route: '/policy' },
      { label: 'Bill checked', todo: 'Check your bill', done: this.bill()?.reviewed === true, route: '/case/bill' },
      { label: 'Papers ready', todo: 'Collect your papers', done: collected, route: '/case', fragment: 'checklist' },
      { label: 'Claim sent', todo: 'Send your claim', done: sent, route: '/case/letter', query: { kind: 'cover_letter' } },
      { label: 'Insurer decided', todo: 'Wait for their decision', done: this.decided(), route: '/case/settlement' },
      { label: 'Letter sent', todo: 'Write to the insurer', done: skip || this.lettersSent().length > 0, route: '/case/letter', query: { kind: this.suggestedLetter() } },
      { label: 'Insurer replied', todo: 'Wait for their reply', done: skip || !!this.lastReply(), route: '/case/reply' },
      { label: 'Claim closed', todo: 'Close the claim', done: this.closed(), route: '/case', fragment: 'diary' },
    ];
  });
  /** The step after the last one done. Earlier open steps stay open but are not "current". */
  readonly currentIndex = computed(() => {
    const steps = this.steps();
    let last = -1;
    steps.forEach((s, i) => {
      if (s.done) last = i;
    });
    return last + 1 < steps.length ? last + 1 : -1;
  });
  readonly current = computed<JourneyStep | null>(() => this.steps()[this.currentIndex()] ?? null);
  readonly doneCount = computed(() => this.steps().filter((s) => s.done).length);

  readonly nextAction = computed<NextAction | null>(() => {
    const c = this.claimCase();
    if (!c) return null;
    const reply = this.lastReply();
    const awaiting = this.awaiting();
    const days = this.waitingDays();
    if (this.closed()) {
      return { tone: 'ok', icon: 'task_alt', title: 'This claim is closed', text: 'You marked it as sorted. Reopen it from the claim diary if anything changes.', action: 'Claim diary', route: '/case', fragment: 'diary' };
    }
    if (awaiting && this.overdue()) {
      return awaiting.kind === 'claim_sent'
        ? { tone: 'bad', icon: 'schedule', title: `No decision ${days} days after you sent the claim`, text: 'Ask the insurer where your claim stands. Quote your claim number.', action: 'Write to the insurer', route: '/case/letter', query: { kind: 'grievance' } }
        : { tone: 'bad', icon: 'schedule', title: `No reply ${days} days after your letter`, text: 'You can complain to the next level now. Check the latest time limit first.', action: 'Next step', route: '/case/letter', query: { kind: 'grievance' }, fragment: 'escalation' };
    }
    if (awaiting) {
      const what = awaiting.kind === 'claim_sent' ? 'decision' : 'reply';
      return { tone: 'info', icon: 'hourglass_top', title: `Waiting for the insurer's ${what}`,
        text: `Sent on ${shortDate(awaiting.date)} (${days} day${days === 1 ? '' : 's'} ago). When they answer, add it here.`, action: 'They replied', route: '/case/reply' };
    }
    if (reply) {
      switch (reply.outcome) {
        case 'paid_more':
          return { tone: 'ok', icon: 'savings', title: reply.newApprovedAmount ? `The insurer will now pay ${formatInr(reply.newApprovedAmount)}` : 'The insurer agreed to pay more',
            text: 'Check the money reaches your bank. Then close the claim.', action: 'See the reply', route: '/case/reply' };
        case 'asks_for_papers':
          return { tone: 'warn', icon: 'description', title: 'The insurer wants more papers', text: (reply.papersAsked ?? []).slice(0, 3).join(', ') || 'See which papers they asked for.', action: 'See the reply', route: '/case/reply' };
        case 'explained':
          return { tone: 'info', icon: 'info', title: 'The insurer explained the cuts', text: 'Read their reason. If you still disagree, you can complain.', action: 'See the reply', route: '/case/reply' };
        case 'unclear':
          return { tone: 'warn', icon: 'help_outline', title: 'The insurer replied', text: "It isn't clear what they decided. Read it, or ask us what it means.", action: 'See the reply', route: '/case/reply' };
        default:
          return { tone: 'bad', icon: 'report', title: 'The insurer kept its decision', text: "You can complain to the insurer's complaints team, then Bima Bharosa.", action: 'Make a complaint', route: '/case/letter', query: { kind: 'grievance' } };
      }
    }
    const r = this.rejection();
    if (r) {
      return { tone: 'bad', icon: 'cancel', title: 'The insurer refused your claim', text: r.reason ? `Their reason: ${r.reason}` : 'See their reason, then ask them to look again.',
        action: 'Ask them to look again', route: '/case/letter', query: { kind: 'reconsideration' } };
    }
    const s = this.settlement();
    if (s && this.cutTotal() > 0) {
      const unclear = s.deductions.filter((d) => d.trust === 'unknown').reduce((sum, d) => sum + d.amount, 0);
      return { tone: unclear ? 'bad' : 'warn', icon: 'help_outline', title: unclear ? `${formatInr(unclear)} cut with no clear reason` : `${formatInr(this.cutTotal())} was cut from your claim`,
        text: 'Ask the insurer to explain. We write the letter; you send it and mark it as sent.', action: 'Write to the insurer', route: '/case/letter', query: { kind: 'clarification' } };
    }
    if (s) {
      return { tone: 'ok', icon: 'task_alt', title: 'The insurer paid in full', text: 'Check the money reached your bank, then close the claim.', action: 'Close the claim', route: '/case', fragment: 'diary' };
    }
    if (!this.bill() && !c.documents.length && !this.timeline().length) {
      const start: NextAction = { tone: 'info', icon: 'upload_file', title: 'Start with the hospital bill', text: 'Add the final bill. We check every charge and fill in your claim.', action: 'Add the hospital bill', route: '/upload', query: { type: 'Hospital bill' } };
      return start;
    }
    return { tone: 'info', icon: 'send', title: 'Send your claim to the insurer', text: 'Use our cover letter, attach your papers, then mark it as sent.', action: 'Cover letter', route: '/case/letter', query: { kind: 'cover_letter' } };
  });
}
