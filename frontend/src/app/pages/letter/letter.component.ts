import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService, isLive } from '../../services/api.service';
import { LetterDraft, LetterKind } from '../../models/models';

const KINDS: { id: LetterKind; label: string; when: string }[] = [
  { id: 'clarification', label: 'Ask why money was deducted', when: 'After a settlement with deductions' },
  { id: 'reconsideration', label: 'Ask to reconsider a rejection', when: 'After the claim was rejected' },
  { id: 'grievance', label: 'Raise a grievance', when: 'When an earlier letter got no proper reply' },
  { id: 'cover_letter', label: 'Claim submission cover letter', when: 'When sending your claim papers' },
];

@Component({
  selector: 'app-letter',
  standalone: true,
  imports: [FormsModule, RouterLink, MatButtonModule, MatIconModule],
  templateUrl: './letter.component.html',
  styles: `
    .meta { display: grid; grid-template-columns: 80px 1fr; gap: 6px 12px; font-size: .9rem; margin-bottom: 12px; }
    .meta span { color: var(--cn-muted); }
    textarea { width: 100%; min-height: 420px; padding: 14px; font: inherit; font-size: .95rem; line-height: 1.6;
               border: 1px solid var(--cn-border); border-radius: 10px; resize: vertical; }
    textarea:focus { outline: 2px solid var(--cn-primary); border-color: transparent; }
    .print-only { display: none; white-space: pre-wrap; }
    .escalation { list-style: none; padding: 0; margin: 0; counter-reset: step; }
    .escalation li { position: relative; padding: 0 0 14px 40px; }
    .escalation li::before { counter-increment: step; content: counter(step); position: absolute; left: 0; top: 0; width: 28px; height: 28px;
                             border-radius: 50%; background: var(--cn-primary-soft); color: var(--cn-primary); font-weight: 700;
                             display: flex; align-items: center; justify-content: center; }
    .kinds { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-bottom: 16px; }
    .kind { text-align: left; border: 1px solid var(--cn-border); border-radius: 12px; padding: 10px 12px; background: #fff; font: inherit; cursor: pointer; }
    .kind.active { border-color: var(--cn-primary); background: var(--cn-primary-soft); }
    .kind:disabled { cursor: not-allowed; opacity: .55; }
    .kind small { display: block; color: var(--cn-muted); }
    .warn { background: var(--cn-warn-soft); color: var(--cn-warn); border-radius: 10px; padding: 8px 12px; margin-bottom: 12px; font-size: .9rem; }
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

  letter = signal<LetterDraft | null>(null);
  claimCase = toSignal(this.api.getCase());
  body = '';
  copied = signal(false);
  kind = signal<LetterKind>('clarification');
  loading = signal(false);
  error = signal<string | null>(null);
  readonly kinds = KINDS;
  /** Demo data has only the clarification letter; the other kinds are written live by the backend. */
  readonly live = isLive('letter');

  constructor() {
    this.load('clarification');
  }

  load(kind: LetterKind): void {
    this.kind.set(kind);
    this.loading.set(true);
    this.error.set(null);
    this.api.getLetter(kind).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (l) => {
        this.letter.set(l);
        this.body = l.body;
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(e?.error?.detail ?? 'Could not draft the letter. Please try again.');
        this.loading.set(false);
      },
    });
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
    if (!l) return this.body;
    const evidence = l.evidenceIndex.map((e, i) => `${i + 1}. ${e}`).join('\n');
    return `To: ${l.to}\nSubject: ${l.subject}\n\n${this.body}\n\nEvidence index\n${evidence}\n`;
  }
}
