import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, catchError, combineLatest, concat, concatMap, delay, from, map, of, shareReplay, switchMap, tap, timeout } from 'rxjs';
import { postEventStream } from './sse';
import { SettingsService } from './settings.service';
import { Workspace, WorkspaceService } from './workspace.service';
import {
  TreatmentPlanInput, TreatmentPlanPreparation, DisputeReviewEvent, DisputePreparation, BillPolicyAnalysis, CoverageEstimate, AgentStep, AnswerCard, AskEvent, Bill, BillItem, BillReview, ChecklistStatus, ClaimCase, ClaimStatus, ClaimSummary, LetterDraft, LetterKind,
  AskRequest, MockQa, MockQuery, PastClaimInput, PolicyDetailsInput, PolicyFacts, QueryEvent, QueryHelp, Settlement, TimelineEvent, TimelineEventInput, UploadEvent,
} from '../models/models';
import { diaryStage, guessReply, sortedTimeline, todayIso } from '../shared/claim-diary';

export type Feature = 'policy' | 'ask' | 'upload' | 'case' | 'bill' | 'settlement' | 'letter' | 'query';

/** Which features have a real backend yet. Only these can be switched to live data on /status. */
export const FEATURES: { id: Feature; label: string; backendReady: boolean }[] = [
  { id: 'policy', label: 'My policy', backendReady: true },
  { id: 'ask', label: 'Ask CareNest', backendReady: true },
  { id: 'upload', label: 'Add documents', backendReady: true },
  { id: 'case', label: 'My claim and papers checklist', backendReady: true },
  { id: 'bill', label: 'Check my bill', backendReady: true },
  { id: 'settlement', label: 'Why money was cut', backendReady: true },
  { id: 'letter', label: 'Write to the insurer', backendReady: true },
  { id: 'query', label: "Insurer's question", backendReady: true },
];

const LIVE_KEY = 'carenest.live';

// Read once at start-up; /status saves a new list and reloads the page.
const LIVE = ((): Set<Feature> => {
  try {
    const saved = localStorage.getItem(LIVE_KEY);
    const defaults = FEATURES.filter((f) => f.backendReady).map((f) => f.id);
    return new Set(saved === null ? defaults : JSON.parse(saved) as Feature[]);
  } catch {
    return new Set(FEATURES.filter((f) => f.backendReady).map((f) => f.id));
  }
})();

export function isLive(feature: Feature): boolean {
  return LIVE.has(feature);
}

export function saveLiveFeatures(features: Feature[]): void {
  localStorage.setItem(LIVE_KEY, JSON.stringify(features));
}

/** True when every feature that has a backend is live (the header shows "Your documents"). */
export function isFullyLive(): boolean {
  return FEATURES.filter((f) => f.backendReady).every((f) => LIVE.has(f.id));
}

export function setAllLive(on: boolean): void {
  saveLiveFeatures(on ? FEATURES.filter((f) => f.backendReady).map((f) => f.id) : []);
}

/** Values for the upload form; 'auto' lets the backend detect the type from page 1. */
export const DOC_TYPES = ['auto', 'Policy document', 'Hospital bill', 'Settlement letter', 'Rejection letter', 'Insurer reply', 'Discharge summary', 'Other'] as const;
export type DocType = (typeof DOC_TYPES)[number];

const STEP_DELAY_MS = 650;
const DEMO_DIARY_KEY = 'carenest.timeline';
const DEMO_TICKS_KEY = 'carenest.checklist';
const DEMO_CLAIMS_KEY = 'carenest.claims';
const DEMO_BILL_REVIEW_KEY = 'carenest.billReview';
const LETTER_DRAFT_PREFIX = 'carenest.letter.';
/** Demo mode: the sample claim's id while a new, empty claim is open. */
export const DEMO_CLAIM_ID = 'cl-demo0001';

interface DemoClaims {
  added: ClaimSummary[];
  removed: string[];
  /** A new, empty claim is open; the sample claim's diary, ticks and bill check wait in `stash`. */
  fresh?: boolean;
  stash?: { timeline: TimelineEvent[]; checklist: Record<string, ChecklistStatus>; billReview?: BillReview | null };
}

function readDemo<T>(key: string, fallback: T): T {
  try {
    return (JSON.parse(localStorage.getItem(key) ?? 'null') as T) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeDemo(key: string, value: unknown): void {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
}

function removeDemo(key: string): void {
  try { localStorage.removeItem(key); } catch { /* private mode */ }
}

function readDemoDiary(): TimelineEvent[] {
  return readDemo<TimelineEvent[]>(DEMO_DIARY_KEY, []);
}

function writeDemoDiary(events: TimelineEvent[]): void {
  writeDemo(DEMO_DIARY_KEY, events);
}

function readDemoClaims(): DemoClaims {
  return readDemo<DemoClaims>(DEMO_CLAIMS_KEY, { added: [], removed: [] });
}

function clearLetterDrafts(prefix: string): void {
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(prefix)) localStorage.removeItem(key);
    }
  } catch { /* private mode */ }
}

function randomHex(bytes: number): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes)), (b) => b.toString(16).padStart(2, '0')).join('');
}

function newEventId(): string {
  return 'ev-' + randomHex(4);
}

/** A stream that re-emits whenever its source is swapped (refresh after an upload, or a saved change). */
function resource<T>(first: Observable<T>): { stream: Observable<T>; set: (next: Observable<T>) => void } {
  const source = new BehaviorSubject<Observable<T>>(first);
  return { stream: source.pipe(switchMap((o) => o), shareReplay(1)), set: (next) => source.next(next) };
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private settings = inject(SettingsService);
  readonly workspace = inject(WorkspaceService);
  readonly workspaceKey = signal('');
  private exampleReady?: Observable<unknown>;

  // Live mode: null means "not uploaded yet" (404).
  private sessionInfo = resource<{ expiresAt: string; mode: 'guest' | 'live_demo' } | null>(of(null));
  getSessionInfo() { return this.sessionInfo.stream; }
  // Welcome/chat is general: do not read any policy/case until a workspace page opens.
  private policy = resource<PolicyFacts | null>(of(null));
  private claim = resource<ClaimCase | null>(of(null));
  private bill = resource<Bill | null>(of(null));
  private settlement = resource<Settlement | null>(of(null));
  private claims = resource<ClaimSummary[] | null>(of(null));

  ensureExampleWorkspace(): Observable<unknown> {
    if (!FEATURES.some((feature) => isLive(feature.id))) {
      this.workspaceKey.set('mock-preview');
      this.refreshPolicy(); this.refreshCase();
      return of({ ready: true, mock: true });
    }
    if (!this.exampleReady) {
      this.exampleReady = this.http.post<{ ready: boolean; workspaceKey: string }>('/api/demo/ensure', {}, { params: { workspace: 'example' } }).pipe(
        tap((ready) => { this.workspaceKey.set(ready.workspaceKey); this.refreshPolicy(); this.refreshCase(); }),
        catchError((error) => { this.exampleReady = undefined; throw error; }),
        shareReplay({ bufferSize: 1, refCount: false }),
      );
    }
    return this.exampleReady;
  }

  private stream<T>(url: string, body: unknown, mode: Workspace = this.workspace.mode()): Observable<T> {
    return postEventStream<T>(this.workspace.url(url, mode), body).pipe(map((event) => this.workspace.links(event, mode)));
  }

  getCoverage(): Observable<CoverageEstimate | null> {
    return combineLatest([this.policy.stream, this.claims.stream]).pipe(
      switchMap(([policy, claims]) => {
        if (isLive('policy') && isLive('case')) return this.http.get<CoverageEstimate>('/api/coverage');
        if (isLive('policy') || isLive('case') || !policy) return of(null);
        return this.http.post<CoverageEstimate>('/api/coverage/preview', {
          policy, claims: (claims ?? []).map((c) => ({ ...c, policyId: policy.policyId })),
        });
      }),
      catchError(() => of(null)),
    );
  }

  getPolicy(): Observable<PolicyFacts | null> { return this.policy.stream; }
  refreshPolicy(): void { this.policy.set(this.loadPolicy()); this.sessionInfo.set(this.http.get<{ expiresAt: string; mode: 'guest' | 'live_demo' }>('/api/session')); }

  /** Every claim: the current one first, then earlier ones, newest first. */
  getClaims(): Observable<ClaimSummary[] | null> { return this.claims.stream; }

  /** Keeps the current claim in the list and starts an empty one. In demo mode the sample claim is put aside in this browser. */
  startNewClaim(): Observable<ClaimSummary[] | null> {
    if (isLive('case')) {
      return this.http.post<ClaimSummary[]>('/api/claims/new', {}).pipe(tap((list) => this.switchedClaim(list)));
    }
    const demo = readDemoClaims();
    if (!demo.fresh) {
      writeDemo(DEMO_CLAIMS_KEY, { ...demo, fresh: true, stash: {
        timeline: readDemoDiary(), checklist: readDemo(DEMO_TICKS_KEY, {}), billReview: readDemo<BillReview | null>(DEMO_BILL_REVIEW_KEY, null) } });
    }
    writeDemoDiary([]);
    writeDemo(DEMO_TICKS_KEY, {});
    removeDemo(DEMO_BILL_REVIEW_KEY);
    return this.demoSwitched();
  }

  /** Makes an earlier claim the current one; the current one moves into the list. Demo mode can only reopen the sample claim. */
  openClaim(id: string): Observable<ClaimSummary[] | null> {
    if (isLive('case')) {
      return this.http.post<ClaimSummary[]>(`/api/claims/${encodeURIComponent(id)}/open`, {}).pipe(tap((list) => this.switchedClaim(list)));
    }
    const { fresh, stash, ...demo } = readDemoClaims();
    if (fresh && id === DEMO_CLAIM_ID) {
      writeDemoDiary(stash?.timeline ?? []);
      writeDemo(DEMO_TICKS_KEY, stash?.checklist ?? {});
      if (stash?.billReview) writeDemo(DEMO_BILL_REVIEW_KEY, stash.billReview);
      writeDemo(DEMO_CLAIMS_KEY, demo);
    }
    return this.demoSwitched();
  }

  /** Adds a claim made before CareNest. Demo mode keeps it in this browser. */
  addPastClaim(input: PastClaimInput): Observable<ClaimSummary[] | null> {
    if (isLive('case')) {
      return this.http.post<ClaimSummary[]>('/api/claims/past', input).pipe(tap((list) => this.claims.set(of(list))));
    }
    const demo = readDemoClaims();
    writeDemo(DEMO_CLAIMS_KEY, { ...demo, added: [...demo.added, pastClaimSummary(input)] });
    return this.reloadClaims();
  }

  /** Deletes an earlier claim (never the current one). Demo mode keeps the change in this browser. */
  deleteClaim(id: string): Observable<ClaimSummary[] | null> {
    if (isLive('case')) {
      return this.http.delete<ClaimSummary[]>(`/api/claims/${encodeURIComponent(id)}`).pipe(tap((list) => this.claims.set(of(list))));
    }
    const demo = readDemoClaims();
    writeDemo(DEMO_CLAIMS_KEY, { ...demo, added: demo.added.filter((c) => c.id !== id), removed: [...demo.removed, id] });
    return this.reloadClaims();
  }

  private switchedClaim(list: ClaimSummary[]): void {
    clearLetterDrafts(LETTER_DRAFT_PREFIX + this.workspaceKey() + '.'); // scoped to this workspace
    this.claims.set(of(list));
    this.reloadClaimData();
  }

  private demoSwitched(): Observable<ClaimSummary[] | null> {
    clearLetterDrafts(LETTER_DRAFT_PREFIX + this.workspaceKey() + '.');
    this.reloadClaimData();
    return this.reloadClaims();
  }

  savePolicyDetails(details: PolicyDetailsInput, current: PolicyFacts): Observable<PolicyFacts> {
    const saved$ = isLive('policy')
      ? this.http.put<PolicyFacts>('/api/policy/details', details)
      : of(mergeDetailsLocally(current, details)); // demo mode: no recompute of waiting-period dates
    return saved$.pipe(tap((facts) => this.policy.set(of(facts))));
  }
  getCase(): Observable<ClaimCase | null> { return this.claim.stream; }
  getBill(): Observable<Bill | null> { return this.bill.stream; }

  /**
   * Saves what the family checked or corrected on the bill. Live: the backend re-runs every check on it.
   * Demo: kept in this browser and shown on the sample bill (its checks stay as they were).
   */
  compareBillPolicy(): Observable<BillPolicyAnalysis> {
    return this.http.post<BillPolicyAnalysis>('/api/case/bill/evidence', {}).pipe(tap(() => this.bill.set(this.loadBill())));
  }

  reviewBill(review: BillReview): Observable<Bill | null> {
    if (isLive('bill')) {
      return this.http.put<Bill>('/api/case/bill', review).pipe(tap((b) => {
        this.bill.set(of(b));
        this.claim.set(this.loadCase());
        this.claims.set(this.loadClaims());
      }));
    }
    writeDemo(DEMO_BILL_REVIEW_KEY, review);
    const next = this.loadBill();
    this.bill.set(next);
    this.claim.set(this.loadCase());
    return next;
  }
  getSettlement(): Observable<Settlement | null> { return this.settlement.stream; }

  prepareTreatmentPlan(input: TreatmentPlanInput): Observable<TreatmentPlanPreparation> {
    return this.http.post<TreatmentPlanPreparation>('/api/policy/treatment-plan/prepare', input);
  }

  reviewDispute(question: string): Observable<DisputeReviewEvent> {
    return this.stream<DisputeReviewEvent>('/api/case/dispute/review/stream', { question, language: this.settings.lang() });
  }

  getDisputePreparation(): Observable<DisputePreparation | null> {
    if (!isLive('settlement')) return of(null);
    return this.http.get<DisputePreparation>('/api/case/dispute/inputs').pipe(catchError(() => of(null)));
  }
  refreshCase(): void {
    this.reloadClaimData();
    this.claims.set(this.loadClaims());
  }

  private reloadClaimData(): void {
    this.claim.set(this.loadCase());
    this.bill.set(this.loadBill());
    this.settlement.set(this.loadOptional<Settlement>('settlement', 'settlement.json', '/api/case/settlement'));
  }

  /** A saved change to the current claim can change its line in the claims list too. */
  private caseSaved(c: ClaimCase): void {
    this.claim.set(of(c));
    this.claims.set(this.loadClaims());
  }
  getLetter(kind: LetterKind = 'clarification'): Observable<LetterDraft> {
    return isLive('letter')
      ? this.http.get<LetterDraft>('/api/case/letter', { params: { kind } })
      : this.http.get<Record<LetterKind, LetterDraft>>('/mocks/letter.json').pipe(map((all) => all[kind]));
  }

  /** Saves a checklist tick. Demo mode keeps it in this browser. */
  updateChecklistItem(id: string, status: ChecklistStatus): Observable<ClaimCase | null> {
    if (!isLive('case')) {
      const ticks = readDemo<Record<string, ChecklistStatus>>(DEMO_TICKS_KEY, {});
      writeDemo(DEMO_TICKS_KEY, { ...ticks, [id]: status });
      return this.reloadCase();
    }
    return this.http.patch<ClaimCase>(`/api/case/checklist/${encodeURIComponent(id)}`, { status }).pipe(tap((c) => this.caseSaved(c)));
  }

  /** Claim diary: "I sent it", "I filed a complaint", "close my claim". Demo mode keeps it in this browser. */
  addTimelineEvent(input: TimelineEventInput): Observable<ClaimCase | null> {
    if (isLive('case')) {
      return this.http.post<ClaimCase>('/api/case/timeline', input).pipe(tap((c) => this.caseSaved(c)));
    }
    writeDemoDiary([...readDemoDiary(), { id: newEventId(), ...input }]);
    return this.reloadCase();
  }

  removeTimelineEvent(id: string): Observable<ClaimCase | null> {
    if (isLive('case')) {
      return this.http.delete<ClaimCase>(`/api/case/timeline/${encodeURIComponent(id)}`).pipe(tap((c) => this.caseSaved(c)));
    }
    writeDemoDiary(readDemoDiary().filter((e) => e.id !== id));
    return this.reloadCase();
  }

  /** Reads the insurer's reply (pasted text) and adds it to the diary. */
  submitReply(text: string): Observable<ClaimCase | null> {
    if (isLive('case')) {
      return this.http.post<ClaimCase>('/api/case/reply', { text }).pipe(tap((c) => this.caseSaved(c)));
    }
    writeDemoDiary([...readDemoDiary(), { id: newEventId(), kind: 'reply', date: todayIso(), source: 'demo', ...guessReply(text) }]);
    return this.reloadCase().pipe(delay(STEP_DELAY_MS));
  }

  private reloadCase(): Observable<ClaimCase | null> {
    const next = this.loadCase();
    this.claim.set(next);
    this.claims.set(this.loadClaims());
    return next;
  }

  private reloadClaims(): Observable<ClaimSummary[] | null> {
    const next = this.loadClaims();
    this.claims.set(next);
    return next;
  }

  getSampleReply(): Observable<string> {
    return this.http.get<{ sampleReply: string }>('/mocks/reply.json').pipe(map((m) => m.sampleReply), catchError(() => of('')));
  }

  ask(question: string, conversationId?: string, mode: Workspace = this.workspace.mode()): Observable<AskEvent> {
    if (isLive('ask')) {
      // Steps arrive as the backend runs them (Server-Sent Events), then the verified answer.
      const body: AskRequest = { question, language: this.settings.lang(), conversationId, generalOnly: mode === 'general' };
      return this.stream<AskEvent>('/api/copilot/ask/stream', body, mode);
    }
    return this.http.get<MockQa[]>('/mocks/qa.json').pipe(
      map((list) => pickAnswer(list, question)),
      switchMap((qa) => concat(
        from(qa.steps).pipe(concatMap((step) => of<AskEvent>({ type: 'step', step }).pipe(delay(STEP_DELAY_MS)))),
        of<AskEvent>({ type: 'answer', answer: qa.answer }).pipe(delay(STEP_DELAY_MS)),
      )),
    );
  }

  uploadDocument(file: File, docType: DocType = 'auto'): Observable<UploadEvent> {
    if (isLive('upload')) {
      const body = new FormData();
      body.append('file', file);
      body.append('docType', docType);
      return this.http.post<{ detectedType: string; pages: number; message?: string | null }>('/api/documents', body).pipe(
        timeout(285000),
        map((r): UploadEvent => ({ type: 'done', detectedType: r.detectedType, pages: r.pages, message: r.message ?? undefined })),
      );
    }
    const steps = ['Uploading securely', 'Reading pages with Document AI', 'Finding clauses and amounts', 'Saving to your case'];
    return concat(
      from(steps).pipe(concatMap((label) => of<UploadEvent>({ type: 'step', label }).pipe(delay(STEP_DELAY_MS)))),
      of<UploadEvent>({ type: 'done', detectedType: docType === 'auto' ? guessType(file.name) : docType, pages: 0 }).pipe(delay(STEP_DELAY_MS)),
    );
  }

  /** Runs the synthetic demo documents through the real backend pipeline, then refreshes cached data. */
  loadDemoCase(): Observable<{ loaded: { file: string; type: string; pages: number; reused: boolean }[] }> {
    return this.http.post<{ loaded: { file: string; type: string; pages: number; reused: boolean }[] }>('/api/demo/load', {}).pipe(
      tap(() => {
        this.refreshPolicy();
        this.refreshCase();
      }),
    );
  }

  getSampleQuery(): Observable<string> {
    return this.http.get<MockQuery>('/mocks/cashless-query.json').pipe(map((m) => m.sampleQuery));
  }

  explainQuery(queryText: string): Observable<QueryEvent> {
    if (isLive('query')) {
      return this.http.post<{ steps: AgentStep[]; help: QueryHelp }>('/api/case/query-help', { queryText }).pipe(
        switchMap((r) => concat(
          from(r.steps).pipe(concatMap((step) => of<QueryEvent>({ type: 'step', step }).pipe(delay(200)))),
          of<QueryEvent>({ type: 'result', help: r.help }),
        )),
      );
    }
    return this.http.get<MockQuery>('/mocks/cashless-query.json').pipe(
      switchMap((m) => concat(
        from(m.steps).pipe(concatMap((step) => of<QueryEvent>({ type: 'step', step }).pipe(delay(STEP_DELAY_MS)))),
        of<QueryEvent>({ type: 'result', help: m.help }).pipe(delay(STEP_DELAY_MS)),
      )),
    );
  }

  private loadPolicy(): Observable<PolicyFacts | null> {
    return this.get<PolicyFacts>('policy', 'policy.json', '/api/policy').pipe(catchError(() => of(null)), shareReplay(1));
  }

  private loadCase(): Observable<ClaimCase | null> {
    const case$ = this.get<ClaimCase>('case', 'case.json', '/api/case');
    return (isLive('case') ? case$ : case$.pipe(map((c) => withDemoDiary(c)))).pipe(catchError(() => of(null)), shareReplay(1));
  }

  private loadBill(): Observable<Bill | null> {
    const bill$ = this.loadOptional<Bill>('bill', 'bill.json', '/api/case/bill');
    return isLive('bill') ? bill$ : bill$.pipe(map((b) => (b ? withDemoReview(b) : b)), shareReplay(1));
  }

  private loadClaims(): Observable<ClaimSummary[] | null> {
    const claims$ = this.get<ClaimSummary[]>('case', 'claims.json', '/api/claims');
    return (isLive('case') ? claims$ : claims$.pipe(map(withDemoClaims))).pipe(catchError(() => of(null)), shareReplay(1));
  }

  private loadOptional<T>(feature: Feature, mockFile: string, apiUrl: string): Observable<T | null> {
    if (!isLive(feature) && readDemoClaims().fresh) return of(null); // the new demo claim has no bill or letter yet
    return this.get<T>(feature, mockFile, apiUrl).pipe(catchError(() => of(null)), shareReplay(1));
  }

  private get<T>(feature: Feature, mockFile: string, apiUrl: string): Observable<T> {
    return this.http.get<T>(isLive(feature) ? apiUrl : `/mocks/${mockFile}`);
  }
}

function withDemoDiary(sample: ClaimCase): ClaimCase {
  const fresh = !!readDemoClaims().fresh;
  const review = fresh ? null : readDemo<BillReview | null>(DEMO_BILL_REVIEW_KEY, null);
  const base = fresh ? blankCase(sample) : sample;
  const c = review ? {
    ...base, patient: { ...base.patient, name: review.patientName || base.patient.name },
    admissionDate: review.admissionDate || base.admissionDate, dischargeDate: review.dischargeDate || base.dischargeDate,
  } : base;
  const timeline = sortedTimeline([...(c.timeline ?? []), ...readDemoDiary()]);
  const ticks = readDemo<Record<string, ChecklistStatus>>(DEMO_TICKS_KEY, {});
  const checklist = c.checklist.map((i) => (ticks[i.id] ? { ...i, status: ticks[i.id] } : i));
  // The sample case already has the insurer's payment letter, so it counts as decided.
  return { ...c, checklist, timeline, stage: diaryStage(timeline, !fresh) ?? c.stage };
}

/** What a new claim looks like before anything is added (same as the backend's empty case). */
function blankCase(sample: ClaimCase): ClaimCase {
  return {
    ...sample, title: 'Your hospital claim', patient: { name: 'Patient', relation: '' }, hospital: 'Hospital not added yet',
    admissionDate: '', dischargeDate: '', diagnosis: 'Not read yet – add the discharge summary', claimType: 'reimbursement',
    claimNumber: '', stage: 'Add your hospital bill to start', documents: [], timeline: [], rejection: null,
    checklist: sample.checklist.filter((i) => i.group === 'claim' && i.id !== 'c4b').map((i) => ({ ...i, status: 'missing' })),
  };
}

/** Demo: the sample bill with the details the family checked in this browser (labels on unchanged lines are kept). */
function withDemoReview(b: Bill): Bill {
  const review = readDemoClaims().fresh ? null : readDemo<BillReview | null>(DEMO_BILL_REVIEW_KEY, null);
  if (!review) return b;
  const items = review.items.map((it, n): BillItem => {
    const before = b.items.find((o) => o.description === it.description);
    return { id: `b${n + 1}`, category: it.category, description: it.description, amount: it.amount, page: it.page,
      tag: before?.tag ?? 'needs_clarification', note: before ? before.note : 'Added by you. The full checks run on your own documents.' };
  });
  return { ...b, hospital: review.hospital || b.hospital, billNumber: review.billNumber ?? b.billNumber, billDate: review.billDate || b.billDate,
    total: review.statedTotal ?? b.total, items, reviewed: true };
}

/** Same rule as the backend's claim_status(). */
function claimStatus(claimed: number | null, approved: number | null): ClaimStatus {
  if (approved === null) return 'in_progress';
  if (approved <= 0) return 'refused';
  return claimed && approved < claimed ? 'part_paid' : 'paid';
}

function pastClaimSummary(p: PastClaimInput): ClaimSummary {
  const claimed = p.claimedAmount ?? null;
  return {
    id: 'cl-' + randomHex(4), source: 'manual', current: false, closed: true,
    title: p.title || 'Hospital claim', patient: p.patient ?? '', hospital: p.hospital ?? '', date: p.date, claimNumber: p.claimNumber ?? '',
    claimedAmount: claimed, approvedAmount: p.approvedAmount, status: claimStatus(claimed, p.approvedAmount),
  };
}

/** Demo list: the mock claims plus changes made in this browser; the demo diary can raise or close the sample claim. */
function withDemoClaims(list: ClaimSummary[]): ClaimSummary[] {
  const { added, removed, fresh, stash } = readDemoClaims();
  const diary = sortedTimeline(fresh ? stash?.timeline : readDemoDiary());
  const raised = diary.filter((e) => e.kind === 'reply' && e.outcome === 'paid_more' && e.newApprovedAmount).at(-1)?.newApprovedAmount;
  const sample = list.filter((c) => c.current).map((c): ClaimSummary => {
    const approved = raised ?? c.approvedAmount;
    return { ...c, approvedAmount: approved, status: claimStatus(c.claimedAmount, approved), closed: diary.at(-1)?.kind === 'closed',
      ...(fresh ? { id: DEMO_CLAIM_ID, current: false } : {}) };
  });
  const earlier = [...(fresh ? sample : []), ...list.filter((c) => !c.current && !removed.includes(c.id)), ...added]
    .sort((a, b) => b.date.localeCompare(a.date));
  // Demo uploads aren't saved, so the new demo claim stays empty and isn't listed.
  return fresh ? earlier : [...sample, ...earlier];
}

function mergeDetailsLocally(p: PolicyFacts, d: PolicyDetailsInput): PolicyFacts {
  const provided = (Object.keys(d) as (keyof PolicyDetailsInput)[]).filter((k) => d[k] !== undefined);
  return {
    ...p,
    startDate: d.startDate ?? p.startDate,
    sumInsured: d.sumInsured ?? p.sumInsured,
    policyNumber: d.policyNumber ?? p.policyNumber,
    members: d.members ?? p.members,
    roomRent: d.roomRentPerDay ? { ...p.roomRent, amount: d.roomRentPerDay } : p.roomRent,
    userProvided: provided,
  };
}

function pickAnswer(list: MockQa[], question: string): MockQa {
  const q = question.toLowerCase();
  const fallback = list.find((qa) => qa.keywords.length === 0) ?? list[list.length - 1];
  let best = fallback;
  let bestScore = 0;
  for (const qa of list) {
    const score = qa.keywords.filter((k) => q.includes(k)).length;
    if (score > bestScore) {
      best = qa;
      bestScore = score;
    }
  }
  return best;
}

function guessType(fileName: string): string {
  const n = fileName.toLowerCase();
  if (n.includes('bill') || n.includes('invoice')) return 'Hospital bill';
  if (n.includes('settle')) return 'Settlement letter';
  if (n.includes('discharge')) return 'Discharge summary';
  if (n.includes('reject') || n.includes('repudiat')) return 'Rejection letter';
  if (n.includes('reply') || n.includes('response')) return 'Insurer reply';
  return 'Policy document';
}
