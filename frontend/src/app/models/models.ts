// Shared data contract between the Angular UI and the FastAPI backend.
// The backend must return exactly these shapes; mock JSON in public/mocks/ follows them too.

export type Verdict = 'covered' | 'partial' | 'not_covered' | 'needs_checking' | 'cant_confirm' | 'info';

/** How strongly the user's own documents support a statement. */
export type Trust = 'supported' | 'check' | 'unknown';

export interface Citation {
  docId: string;
  docName: string;
  page: number;
  clause: string;
  quote: string;
  /** Same-origin URL of the source PDF, if available. */
  docUrl?: string | null;
}

export interface Member {
  name: string;
  relation: string;
  age?: number | null;
}

export interface LimitFact {
  label: string;
  amount?: number;
  unit?: string;
  citation?: Citation;
}

export interface WaitingPeriod {
  id: string;
  label: string;
  kind: 'initial' | 'specific' | 'ped';
  duration: string;
  startDate: string;
  endDate: string;
  appliesTo: string;
  citation: Citation;
}

export interface PolicyTrap {
  title: string;
  explanation: string;
  trust: Trust;
  citation: Citation;
}

export interface PolicyFlag {
  kind: 'missing_pages' | 'outdated' | 'ambiguous';
  message: string;
  citation?: Citation;
  /** Machine-readable reason, e.g. 'missing_start_date'. */
  code?: string | null;
}

export type ProductType = 'health_indemnity' | 'travel' | 'hospital_cash' | 'critical_illness' | 'personal_accident' | 'other';

/** Details from the policy schedule the user can type in; a policy wording often lacks them. */
export interface PolicyDetailsInput {
  startDate?: string;
  sumInsured?: number;
  roomRentPerDay?: number;
  policyNumber?: string;
  members?: Member[];
}

export interface PolicyFacts {
  policyId: string;
  insurer: string;
  planName: string;
  policyNumber: string;
  policyType: string;
  sumInsured: number;
  startDate: string;
  renewalDate: string;
  pageCount: number;
  members: Member[];
  roomRent: LimitFact;
  coPay: LimitFact;
  deductible: LimitFact;
  subLimits: LimitFact[];
  waitingPeriods: WaitingPeriod[];
  traps: PolicyTrap[];
  flags: PolicyFlag[];
  productType: ProductType;
  productNote?: string | null;
  isGroupPolicy?: boolean;
  /** Fields the user entered from their schedule, e.g. ['startDate', 'members']. */
  userProvided?: string[];
}

export interface AgentStep {
  agent: string;
  label: string;
}

export interface AnswerCard {
  verdict: Verdict;
  headline: string;
  summary: string;
  citations: Citation[];
  toConfirm: string[];
  nextAction?: { label: string; route: string };
  secondaryAction?: { label: string; route: string } | null;
  /** From general insurance knowledge, not from the user's own documents. */
  general?: boolean;
}

/** Streamed by /api/copilot/ask: progress steps first, then one answer. */
export type AskEvent = { type: 'step'; step: AgentStep } | { type: 'answer'; answer: AnswerCard };

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text?: string;
  steps?: AgentStep[];
  answer?: AnswerCard;
}

export type BillTag = 'likely_payable' | 'possibly_non_payable' | 'needs_clarification';

export interface BillItem {
  id: string;
  category: string;
  description: string;
  amount: number;
  page: number;
  tag: BillTag;
  note?: string;
}

export interface BillCheck {
  kind: string;
  severity: 'high' | 'medium' | 'info';
  message: string;
  page?: number | null;
}

/** What may not be paid, as a range. Guidance only. */
export interface BillEstimate {
  low: number;
  likely: number;
  high: number;
  lines: string[];
  assumptions: string[];
}

export interface Bill {
  hospital: string;
  billNumber: string;
  billDate: string;
  total: number;
  items: BillItem[];
  pagesRead?: number;
  pagesExpected?: number | null;
  missingPages?: number[];
  checks?: BillCheck[];
  estimate?: BillEstimate;
  docUrl?: string;
  /** false until the family has checked (or corrected) what was read from the bill. */
  reviewed?: boolean;
  /** Lines on the bill whose amount couldn't be read. */
  unreadableLines?: number;
}

export type BillCategory = 'room' | 'icu' | 'nursing' | 'doctor' | 'surgery' | 'anaesthesia' | 'procedure' | 'pharmacy' | 'consumables'
  | 'implants' | 'investigations' | 'equipment' | 'food' | 'admin' | 'other';

export interface BillReviewItem {
  description: string;
  category: BillCategory;
  amount: number;
  rate?: number;
  qty?: number;
  page: number;
}

/** PUT /api/case/bill: what the family checked or corrected; every bill check is re-run on it. */
export interface BillReview {
  hospital?: string;
  billNumber?: string;
  billDate?: string;
  patientName?: string;
  admissionDate?: string;
  dischargeDate?: string;
  statedTotal?: number;
  items: BillReviewItem[];
}

export interface Deduction {
  id: string;
  label: string;
  amount: number;
  insurerReason: string;
  ourReading: string;
  trust: Trust;
  calculation: string[];
  citations: Citation[];
  evidence: string[];
  questions: string[];
}

export interface Settlement {
  claimNumber: string;
  letterDate: string;
  billedAmount: number;
  claimedAmount: number;
  approvedAmount: number;
  deductions: Deduction[];
  reconciliation?: { deductedTotal: number; arithmeticOk: boolean; unexplainedGap: number };
}

export type ChecklistStatus = 'collected' | 'missing' | 'requested';

export interface ChecklistItem {
  id: string;
  name: string;
  source: string;
  why: string;
  status: ChecklistStatus;
  /** 'claim' = needed to file; 'dispute' = needed only to challenge a deduction. */
  group: 'claim' | 'dispute';
}

export interface CaseDocument {
  id: string;
  name: string;
  type: string;
  pages: number;
  uploadedOn: string;
  docUrl?: string;
}

export interface EscalationStep {
  level: number;
  name: string;
  when: string;
  howTo: string;
  link?: string;
  verify: boolean;
}

export interface ClaimCase {
  id: string;
  title: string;
  patient: Member;
  hospital: string;
  admissionDate: string;
  dischargeDate: string;
  diagnosis: string;
  claimType: 'cashless' | 'reimbursement';
  claimNumber: string;
  stage: string;
  documents: CaseDocument[];
  checklist: ChecklistItem[];
  escalation: EscalationStep[];
  /** Claim diary, oldest first. */
  timeline?: TimelineEvent[];
  rejection?: Rejection | null;
}

export interface Rejection {
  reason: string;
  page?: number | null;
  letterDate?: string | null;
  docUrl?: string | null;
}

export type ClaimStatus = 'in_progress' | 'paid' | 'part_paid' | 'refused';

/** One line in the list of claims (GET /api/claims), newest first after the current claim. */
export interface ClaimSummary {
  policyId?: string | null;
  id: string;
  /** 'carenest' = kept here with its files and can be opened again; 'manual' = typed in from a past payment letter. */
  source: 'carenest' | 'manual';
  title: string;
  patient: string;
  hospital: string;
  /** YYYY-MM-DD, the discharge date when known. Decides the policy year the claim counts in. */
  date: string;
  claimNumber: string;
  claimedAmount: number | null;
  /** null while the insurer hasn't decided; 0 if refused. */
  approvedAmount: number | null;
  status: ClaimStatus;
  closed: boolean;
  /** The claim shown on the My claim page. */
  current: boolean;
}

/** A past claim typed in from the insurer's payment letter. */
export interface PastClaimInput {
  date: string;
  approvedAmount: number;
  claimedAmount?: number;
  title?: string;
  patient?: string;
  hospital?: string;
  claimNumber?: string;
}

export type TimelineKind = 'claim_sent' | 'letter_sent' | 'query_answered' | 'complaint_filed' | 'reply' | 'closed';

/** What the insurer's reply means for the family. */
export type ReplyOutcome = 'paid_more' | 'explained' | 'no_change' | 'asks_for_papers' | 'rejected' | 'unclear';

export interface TimelineEvent {
  id: string;
  kind: TimelineKind;
  /** YYYY-MM-DD */
  date: string;
  letterKind?: LetterKind;
  /** Complaint level: 1 insurer, 2 Bima Bharosa, 3 Ombudsman. */
  level?: number;
  reference?: string;
  note?: string;
  outcome?: ReplyOutcome;
  summary?: string;
  newApprovedAmount?: number;
  papersAsked?: string[];
  /** The reply's key sentence, word for word. */
  quote?: string;
  source?: 'pasted' | 'pdf' | 'demo';
  docUrl?: string;
}

export type TimelineEventInput = Pick<TimelineEvent, 'kind' | 'date' | 'letterKind' | 'level' | 'reference' | 'note'>;

export type LetterKind = 'clarification' | 'reconsideration' | 'grievance' | 'cover_letter';

export interface LetterDraft {
  kind: LetterKind;
  to: string;
  subject: string;
  body: string;
  evidenceIndex: string[];
  /** e.g. "Upload the settlement letter so the deductions can be listed." */
  warnings?: string[];
}

export type UploadEvent = { type: 'step'; label: string } | { type: 'done'; detectedType: string; pages: number; message?: string };

/** Plain-language help for an insurer/TPA query raised during a cashless admission. */
export interface QueryHelp {
  queryType: string;
  plainMeaning: string;
  urgency: string;
  documents: { name: string; source: string; why: string }[];
  draftReply: string;
  timelineNote: string;
  citations: Citation[];
}

export type QueryEvent = { type: 'step'; step: AgentStep } | { type: 'result'; help: QueryHelp };

/** Mock-only: a sample query and its prepared help. */
export interface MockQuery {
  sampleQuery: string;
  steps: AgentStep[];
  help: QueryHelp;
}

/** Mock-only: canned answers picked by keyword match. */
export interface MockQa {
  keywords: string[];
  steps: AgentStep[];
  answer: AnswerCard;
}

export interface CoverageEstimate {
  status: 'missing_policy' | 'missing_sum_insured' | 'missing_start_date' | 'not_started' | 'unsupported_product' | 'recorded_only';
  policyId: string | null;
  asOf: string;
  year: { from: string; to: string } | null;
  sumInsured: number | null; used: number | null; remaining: number | null; pct: number | null;
  counted: { id: string; title: string; date: string; approvedAmount: number | null }[];
  excluded: { id: string; reason: string }[];
  pending: boolean; floater: boolean; demo: boolean; historyComplete: boolean; warnings: string[];
}
