import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, concat, concatMap, delay, from, map, of, shareReplay, switchMap } from 'rxjs';
import {
  AnswerCard, AskEvent, Bill, ClaimCase, LetterDraft, MockQa, MockQuery, PolicyFacts, QueryEvent, QueryHelp, Settlement, UploadEvent,
} from '../models/models';

/** Flip to false once the backend implements the /api/* endpoints below. */
export const USE_MOCKS = true;

const STEP_DELAY_MS = 650;

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  private policy$ = this.get<PolicyFacts>('policy.json', '/api/policy').pipe(shareReplay(1));
  private case$ = this.get<ClaimCase>('case.json', '/api/case').pipe(shareReplay(1));
  private bill$ = this.get<Bill>('bill.json', '/api/case/bill').pipe(shareReplay(1));
  private settlement$ = this.get<Settlement>('settlement.json', '/api/case/settlement').pipe(shareReplay(1));

  getPolicy(): Observable<PolicyFacts> { return this.policy$; }
  getCase(): Observable<ClaimCase> { return this.case$; }
  getBill(): Observable<Bill> { return this.bill$; }
  getSettlement(): Observable<Settlement> { return this.settlement$; }
  getLetter(): Observable<LetterDraft> { return this.get<LetterDraft>('letter.json', '/api/case/letter'); }

  ask(question: string): Observable<AskEvent> {
    if (!USE_MOCKS) {
      return this.http.post<AnswerCard>('/api/copilot/ask', { question }).pipe(
        map((answer): AskEvent => ({ type: 'answer', answer })),
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

  uploadDocument(file: File): Observable<UploadEvent> {
    if (!USE_MOCKS) {
      const body = new FormData();
      body.append('file', file);
      return this.http.post<{ detectedType: string; pages: number }>('/api/documents', body).pipe(
        map((r): UploadEvent => ({ type: 'done', ...r })),
      );
    }
    const steps = ['Uploading securely', 'Reading pages with Document AI', 'Finding clauses and amounts', 'Saving to your case'];
    return concat(
      from(steps).pipe(concatMap((label) => of<UploadEvent>({ type: 'step', label }).pipe(delay(STEP_DELAY_MS)))),
      of<UploadEvent>({ type: 'done', detectedType: guessType(file.name), pages: 0 }).pipe(delay(STEP_DELAY_MS)),
    );
  }

  getSampleQuery(): Observable<string> {
    return this.http.get<MockQuery>('/mocks/cashless-query.json').pipe(map((m) => m.sampleQuery));
  }

  explainQuery(queryText: string): Observable<QueryEvent> {
    if (!USE_MOCKS) {
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

  private get<T>(mockFile: string, apiUrl: string): Observable<T> {
    return this.http.get<T>(USE_MOCKS ? `/mocks/${mockFile}` : apiUrl);
  }
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
