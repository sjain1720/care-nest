import { Component, DestroyRef, ElementRef, OnInit, inject, input, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { ChatMessage } from '../../models/models';
import { AgentProgressComponent } from '../../shared/agent-progress.component';
import { AnswerCardComponent } from '../../shared/answer-card.component';

@Component({
  selector: 'app-ask',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatIconModule, AgentProgressComponent, AnswerCardComponent],
  templateUrl: './ask.component.html',
  styles: `
    .page { display: flex; flex-direction: column; min-height: calc(100vh - 140px); }
    .thread { flex: 1; display: flex; flex-direction: column; gap: 12px; }
    .bubble-user { align-self: flex-end; max-width: 80%; background: var(--cn-primary); color: #fff; padding: 10px 14px; border-radius: 16px 16px 4px 16px; }
    .bubble-ai { align-self: stretch; margin-bottom: 0; }
    .empty { text-align: center; padding: 24px 8px; }
    .empty mat-icon { font-size: 48px; width: 48px; height: 48px; color: var(--cn-primary); }
    .prompts { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 12px; }
    .composer { position: sticky; bottom: 0; display: flex; gap: 8px; padding: 12px 0; background: var(--cn-bg); }
    .composer input { flex: 1; min-width: 0; min-height: 48px; padding: 0 14px; font: inherit; border: 1px solid var(--cn-border); border-radius: 12px; background: #fff; }
    .composer button { flex: none; }
    .prompts button { white-space: normal; height: auto; min-height: 40px; padding-top: 6px; padding-bottom: 6px; }
    .composer input:focus { outline: 2px solid var(--cn-primary); border-color: transparent; }
    @media (max-width: 899px) { .composer { bottom: 64px; } }
  `,
})
export class AskComponent implements OnInit {
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);
  private thread = viewChild<ElementRef<HTMLElement>>('thread');

  /** Pre-filled question from ?q= (e.g. from the home page). */
  q = input<string>();

  messages = signal<ChatMessage[]>([]);
  busy = signal(false);
  draft = '';
  private nextId = 1;

  readonly prompts = [
    "Is my father's cataract surgery covered?",
    'What is my room-rent limit?',
    'Why was ₹38,000 deducted?',
    'Which documents am I missing?',
  ];

  ngOnInit(): void {
    const q = this.q();
    if (q) this.send(q);
  }

  send(text: string = this.draft): void {
    const question = text.trim();
    if (!question || this.busy()) return;
    this.draft = '';
    this.busy.set(true);

    const replyId = this.nextId + 1;
    this.messages.update((list) => [
      ...list,
      { id: this.nextId, role: 'user', text: question },
      { id: replyId, role: 'assistant', steps: [] },
    ]);
    this.nextId += 2;
    this.scrollToEnd();

    this.api.ask(question).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (event) => {
        this.patch(replyId, (m) => event.type === 'step'
          ? { ...m, steps: [...(m.steps ?? []), event.step] }
          : { ...m, answer: event.answer });
        this.scrollToEnd();
      },
      error: (e: Error) => {
        this.patch(replyId, (m) => ({ ...m, text: e?.message || 'Sorry, something went wrong. Please try again.' }));
        this.busy.set(false);
      },
      complete: () => this.busy.set(false),
    });
  }

  private patch(id: number, fn: (m: ChatMessage) => ChatMessage): void {
    this.messages.update((list) => list.map((m) => (m.id === id ? fn(m) : m)));
  }

  private scrollToEnd(): void {
    setTimeout(() => this.thread()?.nativeElement.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'end' }));
  }
}
