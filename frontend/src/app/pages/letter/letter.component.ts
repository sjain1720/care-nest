import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { combineLatest, take } from 'rxjs';
import { ApiService } from '../../services/api.service';
import { DiaryActionsService } from '../../services/diary-actions.service';
import { JourneyService } from '../../services/journey.service';
import { LetterDraft, LetterKind, TimelineEvent, TimelineEventInput } from '../../models/models';
import { SkeletonComponent } from '../../shared/page-states.component';
import { LETTER_LABELS, suggestLetter, todayIso } from '../../shared/claim-diary';

const KINDS: { id: LetterKind; label: string; when: string }[] = [
  { id: 'document_response', label: LETTER_LABELS.document_response, when: 'The insurer requested more documents' },
  { id: 'cover_letter', label: LETTER_LABELS.cover_letter, when: 'You are sending your claim papers' },
  { id: 'clarification', label: LETTER_LABELS.clarification, when: 'The insurer paid less than you claimed' },
  { id: 'reconsideration', label: LETTER_LABELS.reconsideration, when: 'The insurer said no to your claim' },
  { id: 'grievance', label: LETTER_LABELS.grievance, when: 'No reply, or a reply that doesn\'t help' },
];
const KIND_IDS = new Set<string>(KINDS.map((k) => k.id));
const BLANK = /\[[^\]\n]{1,60}\]/g;
const DRAFT_KEY = 'carenest.letter.';

@Component({
  selector: 'app-letter',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatIconModule, SkeletonComponent, TranslatePipe],
  templateUrl: './letter.component.html',
  styles: `
    .meta { display: grid; grid-template-columns: 80px 1fr; gap: 6px 12px; font-size: .9rem; margin-bottom: 12px; }
    .meta span { color: var(--cn-muted); }
    textarea { width: 100%; min-height: 420px; padding: 14px; font: inherit; font-size: .95rem; line-height: 1.6;
               border: 1px solid var(--cn-border); border-radius: 10px; resize: vertical; }
    textarea:focus { outline: 2px solid var(--cn-primary); border-color: transparent; }
    .print-only { display: none; white-space: pre-wrap; }
    .escalation { list-style: none; padding: 0; margin: 0; counter-reset: step; }
    .escalation a { display: inline-flex; align-items: center; min-height: 44px; }
    .escalation a.ext { gap: 4px; }
    .escalation a.ext mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .escalation li { position: relative; padding: 0 0 14px 40px; }
    .escalation li::before { counter-increment: step; content: counter(step); position: absolute; left: 0; top: 0; width: 28px; height: 28px;
                             border-radius: 50%; background: var(--cn-primary-soft); color: var(--cn-primary); font-weight: 700;
                             display: flex; align-items: center; justify-content: center; }
    .kinds { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-bottom: 16px; }
    .kind { text-align: left; border: 1px solid var(--cn-border); border-radius: 12px; padding: 10px 12px; background: var(--cn-surface); color: inherit; font: inherit; cursor: pointer; }
    .kind.active { border-color: var(--cn-primary); background: var(--cn-primary-soft); }
    .kind:disabled { cursor: not-allowed; opacity: .55; }
    .kind small { display: block; color: var(--cn-muted); }
    .warn { background: var(--cn-warn-soft); color: var(--cn-warn); border-radius: 10px; padding: 8px 12px; margin-bottom: 12px; font-size: .9rem; }
    .note { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; background: var(--cn-primary-soft); border-radius: 10px; padding: 6px 12px; margin-bottom: 12px; font-size: .9rem; }
    .blank { font-family: inherit; font-weight: 600; }
    .mark { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; margin-top: 8px; }
    .mark label { display: flex; flex-direction: column; gap: 4px; font-size: .85rem; color: var(--cn-muted); }
    .mark input { min-height: 44px; padding: 0 10px; font: inherit; color: var(--cn-ink); border: 1px solid var(--cn-border); border-radius: 10px; background: var(--cn-field); }
    .sent-row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; padding: 6px 0; border-top: 1px solid var(--cn-border); font-size: .9rem; }
    .sent-row:first-of-type { border-top: 0; }
    .sent-row mat-icon { color: var(--cn-ok); }
    .filed { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 6px; }
    @media print {
      textarea { display: none; }
      .print-only { display: block; }
      .card { box-shadow: none; border: 0; }
    }
  `,
})
export class LetterComponent {
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);
  private router = inject(Router);
  private diary = inject(DiaryActionsService);
  readonly journey = inject(JourneyService);

  letter = signal<LetterDraft | null>(null);
  readonly claimCase = this.journey.claimCase;
  readonly body = signal('');
  readonly edited = signal(false);
  readonly blanks = computed(() => [...new Set(this.body().match(BLANK) ?? [])]);
  readonly supportingDocuments = computed(() => (this.letter()?.evidenceIndex ?? []).filter(e => !e.startsWith('Policy wording')));
  readonly policyEvidence = computed(() => (this.letter()?.evidenceIndex ?? []).filter(e => e.startsWith('Policy wording')));
  copied = signal(false);
  kind = signal<LetterKind>('clarification');
  loading = signal(false);
  error = signal<string | null>(null);
  readonly kinds = KINDS;
  readonly previousDrafts = signal<string[]>([]);
  private draftScope = '';
  private loadVersion = 0;
  private loadedWorkspace = '';
  readonly today = todayIso();

  // "I've sent it" and "I've filed here" forms.
  readonly sentDate = signal(todayIso());
  readonly sentRef = signal('');
  readonly saving = signal(false);
  readonly filing = signal<number | null>(null);
  readonly fileDate = signal(todayIso());
  readonly fileRef = signal('');

  /** Diary entries for the letter that is open. */
  readonly sentForKind = computed(() => this.journey.timeline().filter((e) => this.matches(e, this.kind())));

  constructor() {
    const route = inject(ActivatedRoute);
    route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((q) => {
      if (this.loadedWorkspace !== this.api.workspaceKey()) {
        this.loadedWorkspace = this.api.workspaceKey();
        this.letter.set(null);
      }
      const wanted = q.get('kind');
      if (wanted && KIND_IDS.has(wanted)) {
        if (wanted !== this.kind() || !this.letter()) this.load(wanted as LetterKind);
      } else if (!this.letter() && !this.loading()) {
        // No kind in the link: open the letter that fits the claim right now.
        this.loading.set(true);
        combineLatest([this.api.getCase(), this.api.getSettlement()]).pipe(take(1), takeUntilDestroyed(this.destroyRef))
          .subscribe(([c, s]) => this.load(suggestLetter(c, s)));
      }
    });
  }

  choose(kind: LetterKind): void {
    this.router.navigate([], { queryParams: { kind }, queryParamsHandling:'merge', replaceUrl: true });
  }

  load(kind: LetterKind): void {
    const version = ++this.loadVersion;
    const workspaceKey = this.api.workspaceKey();
    this.letter.set(null);
    this.kind.set(kind);
    this.loading.set(true);
    this.error.set(null);
    this.api.getLetter(kind).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (l) => {
        if (version !== this.loadVersion || workspaceKey !== this.api.workspaceKey()) return;
        this.letter.set(l);
        this.draftScope = l.inputFingerprint ?? l.claimKey ?? '';
        const saved = readDraft(kind, this.api.workspaceKey(), this.draftScope);
        const prefix = DRAFT_KEY + this.api.workspaceKey() + '.' + kind;
        try { this.previousDrafts.set(Object.keys(localStorage).filter(k => k.startsWith(prefix) && k !== prefix + (this.draftScope ? '.' + this.draftScope : '')).map(k => localStorage.getItem(k) ?? '').filter(Boolean)); } catch { this.previousDrafts.set([]); }
        this.body.set(saved ?? l.body);
        this.edited.set(saved !== null && saved !== l.body);
        this.loading.set(false);
      },
      error: (e) => {
        if (version !== this.loadVersion || workspaceKey !== this.api.workspaceKey()) return;
        this.error.set(e?.error?.detail ?? 'Could not draft the letter. Please try again.');
        this.loading.set(false);
      },
    });
  }

  onEdit(text: string): void {
    this.body.set(text);
    this.edited.set(true);
    try { if (this.api.workspaceKey()) localStorage.setItem(DRAFT_KEY + this.api.workspaceKey() + '.' + this.kind() + (this.draftScope ? '.' + this.draftScope : ''), text); } catch { /* private mode */ }
  }

  freshDraft(): void {
    try { localStorage.removeItem(DRAFT_KEY + this.api.workspaceKey() + '.' + this.kind() + (this.draftScope ? '.' + this.draftScope : '')); } catch { /* private mode */ }
    this.body.set(this.letter()?.body ?? '');
    this.edited.set(false);
  }

  markSent(): void {
    const kind = this.kind();
    const input: TimelineEventInput = kind === 'cover_letter' ? { kind: 'claim_sent', date: this.sentDate() }
      : kind === 'grievance' ? { kind: 'complaint_filed', level: 1, date: this.sentDate() }
      : { kind: 'letter_sent', letterKind: kind, date: this.sentDate() };
    this.save({ ...input, ...(kind === 'document_response' ? {claimKey:this.letter()?.claimKey,inputFingerprint:this.letter()?.inputFingerprint,replyId:this.letter()?.replyId} : {}), reference: this.sentRef().trim() || undefined }, () => this.sentRef.set(''));
  }

  filedAt(level: number): TimelineEvent | null {
    return [...this.journey.timeline()].reverse().find((e) => e.kind === 'complaint_filed' && (e.level ?? 1) === level) ?? null;
  }

  startFiling(level: number): void {
    this.fileDate.set(todayIso());
    this.fileRef.set('');
    this.filing.set(level);
  }

  markFiled(level: number): void {
    this.save({ kind: 'complaint_filed', level, date: this.fileDate(), reference: this.fileRef().trim() || undefined }, () => this.filing.set(null));
  }

  undo(id: string): void {
    this.api.removeTimelineEvent(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  private save(input: TimelineEventInput, done: () => void): void {
    if (!input.date) return;
    this.saving.set(true);
    this.diary.add(input).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.saving.set(false);
        done();
      },
      error: (e) => { this.saving.set(false); this.error.set(e?.error?.detail ?? 'Could not save this diary entry.'); },
    });
  }

  private matches(e: TimelineEvent, kind: LetterKind): boolean {
    if (kind === 'cover_letter') return e.kind === 'claim_sent';
    if (kind === 'grievance') return e.kind === 'complaint_filed' && (e.level ?? 1) === 1;
    return e.kind === 'letter_sent' && e.letterKind === kind;
  }

  async copy(): Promise<void> {
    await navigator.clipboard.writeText(this.fullText());
    this.copied.set(true);
    setTimeout(() => this.copied.set(false), 2000);
  }

  download(): void {
    const blob = new Blob([this.fullText()], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'carenest-letter-to-insurer.txt';
    a.click();
    URL.revokeObjectURL(url);
  }

  print(): void {
    window.print();
  }

  private fullText(): string {
    const l = this.letter();
    if (!l) return this.body();
    const evidence = l.evidenceIndex.map((e, i) => `${i + 1}. ${e}`).join('\n');
    return `To: ${l.to}\nSubject: ${l.subject}\n\n${this.body()}\n\nEvidence index\n${evidence}\n`;
  }
}

/** The user's edited letter, kept only in this browser. */
function readDraft(kind: LetterKind, workspaceKey: string, scope = ''): string | null {
  try {
    return workspaceKey ? localStorage.getItem(DRAFT_KEY + workspaceKey + '.' + kind + (scope ? '.' + scope : '')) : null;
  } catch {
    return null;
  }
}
