import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, concat, concatMap, delay, from, map, of, shareReplay, switchMap, tap } from 'rxjs';
import {
  AgentStep, AnswerCard, AskEvent, Bill, ClaimCase, LetterDraft, MockQa, MockQuery, PolicyDetailsInput, PolicyFacts, QueryEvent, QueryHelp,
  Settlement, UploadEvent,
} from '../models/models';

export type Feature = 'policy' | 'ask' | 'upload' | 'case' | 'bill' | 'settlement' | 'letter' | 'query';

/** Which features have a real backend yet. Only these can be switched to live data on /status. */
export const FEATURES: { id: Feature; label: string; backendReady: boolean }[] = [
  { id: 'policy', label: 'My policy (facts, traps, waiting periods)', backendReady: true },
  { id: 'ask', label: 'Ask (policy questions)', backendReady: true },
  { id: 'upload', label: 'Upload documents', backendReady: true },
  { id: 'case', label: 'My case and checklist', backendReady: true },
  { id: 'bill', label: 'Hospital bill check', backendReady: true },
  { id: 'settlement', label: 'Settlement breakdown', backendReady: true },
  { id: 'letter', label: 'Letter to insurer', backendReady: false },
  { id: 'query', label: 'Insurer query helper', backendReady: false },
];

const LIVE_KEY = 'carenest.live';

// Read once at start-up; /status saves a new list and reloads the page.
const LIVE = ((): Set<Feature> => {
  try {
    return new Set(JSON.parse(localStorage.getItem(LIVE_KEY) ?? '[]') as Feature[]);
  } catch {
    return new Set<Feature>();
  }
})();

export function isLive(feature: Feature): boolean {
  return LIVE.has(feature);
}

export function saveLiveFeatures(features: Feature[]): void {
  localStorage.setItem(LIVE_KEY, JSON.stringify(features));
}

/** Values for the upload form; 'auto' lets the backend detect the type from page 1. */
export const DOC_TYPES = ['auto', 'Policy document', 'Hospital bill', 'Settlement letter', 'Rejection letter', 'Discharge summary', 'Other'] as const;
export type DocType = (typeof DOC_TYPES)[number];

const STEP_DELAY_MS = 650;

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  // Live mode: null means "not uploaded yet" (404).
  private policy$ = this.loadPolicy();
  private case$ = this.loadCase();
  private bill$ = this.loadOptional<Bill>('bill', 'bill.json', '/api/case/bill');
  private settlement$ = this.loadOptional<Settlement>('settlement', 'settlement.json', '/api/case/settlement');

  getPolicy(): Observable<PolicyFacts | null> { return this.policy$; }
  refreshPolicy(): void { this.policy$ = this.loadPolicy(); }

  savePolicyDetails(details: PolicyDetailsInput, current: PolicyFacts): Observable<PolicyFacts> {
    const saved$ = isLive('policy')
      ? this.http.put<PolicyFacts>('/api/policy/details', details)
      : of(mergeDetailsLocally(current, details)); // demo mode: no recompute of waiting-period dates
    return saved$.pipe(tap((facts) => (this.policy$ = of(facts).pipe(shareReplay(1)))));
  }
  getCase(): Observable<ClaimCase> { return this.case$; }
  getBill(): Observable<Bill | null> { return this.bill$; }
  getSettlement(): Observable<Settlement | null> { return this.settlement$; }
  refreshCase(): void {
    this.case$ = this.loadCase();
    this.bill$ = this.loadOptional<Bill>('bill', 'bill.json', '/api/case/bill');
    this.settlement$ = this.loadOptional<Settlement>('settlement', 'settlement.json', '/api/case/settlement');
  }
  getLetter(): Observable<LetterDraft> { return this.get<LetterDraft>('letter', 'letter.json', '/api/case/letter'); }

  ask(question: string): Observable<AskEvent> {
    if (isLive('ask')) {
      // The backend returns the steps it actually ran plus the answer; replay the steps quickly for the progress list.
      return this.http.post<{ steps: AgentStep[]; answer: AnswerCard }>('/api/copilot/ask', { question }).pipe(
        switchMap((r) => concat(
          from(r.steps).pipe(concatMap((step) => of<AskEvent>({ type: 'step', step }).pipe(delay(200)))),
          of<AskEvent>({ type: 'answer', answer: r.answer }),
        )),
      );
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
        map((r): UploadEvent => ({ type: 'done', detectedType: r.detectedType, pages: r.pages, message: r.message ?? undefined })),
      );
    }
    const steps = ['Uploading securely', 'Reading pages with Document AI', 'Finding clauses and amounts', 'Saving to your case'];
    return concat(
      from(steps).pipe(concatMap((label) => of<UploadEvent>({ type: 'step', label }).pipe(delay(STEP_DELAY_MS)))),
      of<UploadEvent>({ type: 'done', detectedType: docType === 'auto' ? guessType(file.name) : docType, pages: 0 }).pipe(delay(STEP_DELAY_MS)),
    );
  }

  getSampleQuery(): Observable<string> {
    return this.http.get<MockQuery>('/mocks/cashless-query.json').pipe(map((m) => m.sampleQuery));
  }

  explainQuery(queryText: string): Observable<QueryEvent> {
    if (isLive('query')) {
      return this.http.post<QueryHelp>('/api/case/query-help', { queryText }).pipe(
        map((help): QueryEvent => ({ type: 'result', help })),
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

  private loadCase(): Observable<ClaimCase> {
    return this.get<ClaimCase>('case', 'case.json', '/api/case').pipe(shareReplay(1));
  }

  private loadOptional<T>(feature: Feature, mockFile: string, apiUrl: string): Observable<T | null> {
    return this.get<T>(feature, mockFile, apiUrl).pipe(catchError(() => of(null)), shareReplay(1));
  }

  private get<T>(feature: Feature, mockFile: string, apiUrl: string): Observable<T> {
    return this.http.get<T>(isLive(feature) ? apiUrl : `/mocks/${mockFile}`);
  }
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
  return 'Policy document';
}
