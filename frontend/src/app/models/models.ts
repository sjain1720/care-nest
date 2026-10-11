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
  age: number;
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

export interface Bill {
  hospital: string;
  billNumber: string;
  billDate: string;
  total: number;
  items: BillItem[];
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

export type UploadEvent = { type: 'step'; label: string } | { type: 'done'; detectedType: string; pages: number };

/** Mock-only: canned answers picked by keyword match. */
export interface MockQa {
  keywords: string[];
  steps: AgentStep[];
  answer: AnswerCard;
}
