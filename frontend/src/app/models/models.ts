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
}

export interface LetterDraft {
  kind: 'clarification' | 'reconsideration' | 'grievance' | 'cover_letter';
  to: string;
  subject: string;
  body: string;
  evidenceIndex: string[];
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
