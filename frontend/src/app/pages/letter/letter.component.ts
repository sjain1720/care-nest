import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { LetterDraft } from '../../models/models';

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

  constructor() {
    this.api.getLetter().pipe(takeUntilDestroyed(this.destroyRef)).subscribe((l) => {
      this.letter.set(l);
      this.body = l.body;
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
