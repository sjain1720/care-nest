import { ClaimCase, LetterKind, ReplyOutcome, Settlement, TimelineEvent } from '../models/models';

/** Usual waits; the UI asks users to check the latest rule before acting on them. */
export const REPLY_DAYS = 14;
export const DECISION_DAYS = 30;

export const LETTER_LABELS: Record<LetterKind, string> = {
  clarification: 'Ask why money was cut',
  reconsideration: 'Ask them to look again at a rejection',
  grievance: 'Make a complaint',
  cover_letter: 'Cover letter for your claim',
  document_response: 'Response to requested documents',
};

export const COMPLAINT_PLACES: Record<number, string> = {
  1: "the insurer's complaints team",
  2: 'Bima Bharosa',
  3: 'the Insurance Ombudsman',
};

export const OUTCOME_META: Record<ReplyOutcome, { label: string; tone: 'ok' | 'warn' | 'bad' | 'info'; icon: string }> = {
  paid_more: { label: 'An approved amount is stated', tone: 'ok', icon: 'savings' },
  explained: { label: 'They explained the cuts', tone: 'info', icon: 'info' },
  no_change: { label: 'No change to their decision', tone: 'bad', icon: 'block' },
  asks_for_papers: { label: 'They want more papers', tone: 'warn', icon: 'description' },
  rejected: { label: 'They still refuse', tone: 'bad', icon: 'cancel' },
  unclear: { label: 'Not clear what they decided', tone: 'warn', icon: 'help_outline' },
};

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function daysSince(iso: string): number {
  const then = Date.parse(iso + 'T00:00:00');
  const now = Date.parse(todayIso() + 'T00:00:00');
  return Number.isNaN(then) ? 0 : Math.max(0, Math.round((now - then) / 86_400_000));
}

export function shortDate(iso: string): string {
  const t = Date.parse(iso + 'T00:00:00');
  return Number.isNaN(t) ? iso : new Date(t).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

export function sortedTimeline(events: TimelineEvent[] | undefined): TimelineEvent[] {
  return [...(events ?? [])].sort((a, b) => a.date.localeCompare(b.date));
}

/** One line for the claim diary. */
export function eventText(e: TimelineEvent): string {
  switch (e.kind) {
    case 'claim_sent': return 'You sent your claim to the insurer';
    case 'letter_sent': return e.letterKind ? `You sent a letter: ${LETTER_LABELS[e.letterKind].toLowerCase()}` : 'You sent papers or a letter to the insurer';
    case 'complaint_filed': return `You complained to ${COMPLAINT_PLACES[e.level ?? 1] ?? COMPLAINT_PLACES[1]}`;
    case 'query_answered': return "You answered the insurer's question";
    case 'reply': return `The insurer replied: ${OUTCOME_META[e.outcome ?? 'unclear'].label.toLowerCase()}`;
    case 'closed': return 'You closed this claim';
    case 'outcome_recorded': return 'You recorded an outcome update';
    case 'payment_recorded': return `Total payment received so far: ₹${(e.paymentAmount ?? 0).toLocaleString('en-IN')}, recorded by you`;
  }
}

/** Mirrors backend claim_tracker.stage_from_timeline, for demo mode. */
export function diaryStage(all: TimelineEvent[], hasDecision: boolean): string | null {
  const lifecycle = all.filter(e => e.kind !== 'outcome_recorded' && e.kind !== 'payment_recorded');
  const events = hasDecision ? lifecycle.filter((e) => e.kind !== 'query_answered') : lifecycle;
  const latest = events[events.length - 1];
  if (!latest) return null;
  const n = daysSince(latest.date);
  const ago = `${n} day${n === 1 ? '' : 's'} ago`;
  switch (latest.kind) {
    case 'closed': return 'Closed – you marked this claim as sorted';
    case 'reply': {
      const stage = { paid_more: 'The insurer agreed to pay more', explained: 'The insurer explained the cuts', no_change: 'The insurer kept its decision – you can complain',
        asks_for_papers: 'The insurer asked for more papers', rejected: 'The insurer still refuses – you can complain', unclear: 'The insurer replied – read what it says' }[latest.outcome ?? 'unclear'];
      return latest.outcome === 'paid_more' && latest.newApprovedAmount
        ? `${stage} (now ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(latest.newApprovedAmount)})` : stage;
    }
    case 'claim_sent':
      if (hasDecision) return null;
      return n > DECISION_DAYS ? `Claim sent ${n} days ago – no decision yet, ask the insurer` : `Claim sent on ${shortDate(latest.date)} – waiting for the insurer's decision`;
    case 'query_answered': return `You answered the insurer's question on ${shortDate(latest.date)} – waiting for approval`;
    case 'complaint_filed':
      if ((latest.level ?? 1) >= 2) return `Complaint filed with ${COMPLAINT_PLACES[latest.level!]} on ${shortDate(latest.date)} – waiting for their reply`;
      return n > REPLY_DAYS ? `No reply after ${n} days – you can complain to the next level` : `Waiting for the insurer's reply (sent ${shortDate(latest.date)}, ${ago})`;
    case 'outcome_recorded': return null;
    case 'payment_recorded': return null;
    case 'letter_sent':
      return n > REPLY_DAYS ? `No reply after ${n} days – you can complain to the next level` : `Waiting for the insurer's reply (sent ${shortDate(latest.date)}, ${ago})`;
  }
}

/** The letter that fits the claim right now. */
export function suggestLetter(c: ClaimCase | null | undefined, s: Settlement | null | undefined): LetterKind {
  const events = sortedTimeline(c?.timeline);
  const lastReply = [...events].reverse().find((e) => e.kind === 'reply');
  if (lastReply && (lastReply.outcome === 'no_change' || lastReply.outcome === 'rejected')) return 'grievance';
  const lastSent = [...events].reverse().find((e) => e.kind === 'letter_sent');
  if (lastSent && !lastReply && daysSince(lastSent.date) > REPLY_DAYS) return 'grievance';
  if (lastReply?.outcome === 'asks_for_papers') return 'document_response';
  if (c?.rejection) return 'reconsideration';
  if (s) return 'clarification';
  return 'cover_letter';
}

const DEMO_SUMMARY: Record<ReplyOutcome, string> = {
  paid_more: 'The insurer agrees to pay more. Check the new amount reaches your bank.',
  explained: 'The insurer explains why the money was cut and pays nothing more. Check their reason against your policy.',
  no_change: 'The insurer keeps its decision. You can complain to its complaints team, then Bima Bharosa.',
  asks_for_papers: 'The insurer wants more papers before it decides. Send them quickly and keep a copy.',
  rejected: 'The insurer still refuses the claim. You can complain to the next level.',
  unclear: "We couldn't tell what the insurer decided. Read their words, or ask us.",
};

/** Demo mode only: a rough reading by keywords. Live mode asks Gemini. */
export function guessReply(text: string): Pick<TimelineEvent, 'outcome' | 'summary' | 'newApprovedAmount' | 'papersAsked' | 'quote' | 'reference'> {
  const t = text.toLowerCase();
  const amount = /(?:₹|rs\.?|inr)\s?([\d,]{4,})/i.exec(text);
  const ref = /reference (?:number|no\.?)?\s*(?:is\s*)?([A-Z0-9][A-Z0-9/-]{4,})/i.exec(text);
  let outcome: ReplyOutcome = 'unclear';
  if (/additional (amount|payment)|revised|will be (paid|released)|reconsidered and approved/.test(t)) outcome = 'paid_more';
  else if (/(please )?(submit|provide|send|furnish).{0,40}(document|report|certificate|note|papers)/.test(t)) outcome = 'asks_for_papers';
  else if (/repudiat|rejection (is|stands)|unable to (accept|admit)|stands rejected/.test(t)) outcome = 'rejected';
  else if (/(decision|deduction)s? (is|are|stands?) (upheld|correct|final)|no change|regret/.test(t)) outcome = 'no_change';
  else if (/deducted (as|because|under)|as per (clause|policy)|non-payable|proportionate/.test(t)) outcome = 'explained';
  const sentences = text.split(/(?<=[.!?])(?<!\b(?:Rs|No|Dr|Mr|Mrs|Ms)\.)\s+|\n+/i).map((s) => s.trim()).filter((s) => s.split(/\s+/).length >= 8);
  const sentence = sentences.find((s) => /non-payable|reject|repudiat|approv|submit|provide|additional|revised/i.test(s))
    ?? sentences.find((s) => /deduct|pay|paid/i.test(s)) ?? sentences[0] ?? '';
  return {
    outcome,
    summary: `${DEMO_SUMMARY[outcome]} (Demo mode sorts replies by key words only. Live mode reads the whole reply.)`,
    newApprovedAmount: outcome === 'paid_more' && amount ? Number(amount[1].replace(/,/g, '')) : undefined,
    papersAsked: [],
    quote: sentence.slice(0, 300),
    reference: ref?.[1],
  };
}
