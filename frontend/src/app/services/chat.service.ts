import { Injectable, inject, signal } from '@angular/core';
import { Subscription, filter } from 'rxjs';
import { NavigationEnd, Router } from '@angular/router';
import { ApiService, isLive } from './api.service';
import { ChatMessage } from '../models/models';

const GENERAL_PROMPTS = ['What is a waiting period?', 'How do I question a deduction?', 'What documents help prepare a claim?'];

const CONTEXT: { prefix: string; label: string; prompts: string[] }[] = [
  { prefix: '/case/settlement', label: 'Ask about your deductions', prompts: ['Why was money deducted from my claim?', 'Which deduction can I challenge?', 'What should I ask the insurer?'] },
  { prefix: '/case/bill', label: 'Ask about your bill', prompts: ['How much will I have to pay from this bill?', 'Which charges may not be paid?', 'Why does the room rent matter?'] },
  { prefix: '/case/query', label: 'Ask about the insurer query', prompts: ['The TPA sent a query on my pre-auth, what do I do?', 'How fast must I reply to a query?'] },
  { prefix: '/case/letter', label: 'Ask about your letter', prompts: ['What should my letter to the insurer say?', 'Why was money deducted from my claim?'] },
  { prefix: '/case/reply', label: "Ask about the insurer's reply", prompts: ["What does the insurer's reply mean for my claim?", 'Which deduction can I challenge?', 'Why was money deducted from my claim?'] },
  { prefix: '/case', label: 'Ask about your claim', prompts: ['Which documents am I missing?', 'How do I file my claim?', 'Why was money deducted from my claim?'] },
  { prefix: '/policy', label: 'Ask about your cover', prompts: ['What is my room-rent limit?', "Is my father's cataract surgery covered?", 'Is diabetes treatment covered?'] },
];

/** Suggested questions and the floating button's label for the page the user is on. */
export function chatContext(path: string): { label: string; prompts: string[] } {
  return CONTEXT.find((c) => path.startsWith(c.prefix)) ?? { label: 'Ask CareNest', prompts: GENERAL_PROMPTS };
}

const FOLLOW_UPS: Record<string, string[]> = {
  '/case/settlement': ['Which documents am I missing?', 'How much will I have to pay from this bill?', 'What is my room-rent limit?'],
  '/case/letter': ['Which documents am I missing?', 'How much will I have to pay from this bill?', 'What is my room-rent limit?'],
  '/case/reply': ['Which deduction can I challenge?', 'Which documents am I missing?', 'What is my room-rent limit?'],
  '/case/bill': ['Why was money deducted from my claim?', 'Which documents am I missing?', 'What is my room-rent limit?'],
  '/case': ['Why was money deducted from my claim?', 'How much will I have to pay from this bill?'],
  '/policy': ['Is diabetes treatment covered?', 'What is my room-rent limit?', 'Why was money deducted from my claim?'],
};

/** Two or three useful next questions after an answer, without repeating the one just asked. */
export function followUps(route: string | undefined, asked: string): string[] {
  const list = (route && FOLLOW_UPS[route]) || GENERAL_PROMPTS;
  return list.filter((q) => q.toLowerCase() !== asked.trim().toLowerCase()).slice(0, 3);
}

/** One conversation shared by the floating chat and the Ask page, so switching between them keeps the thread. */
@Injectable({ providedIn: 'root' })
export class ChatService {
  private api = inject(ApiService);
  private router = inject(Router);
  private returnUrl = '/';
  private previousPath = '/';
  private sub?: Subscription;
  private nextId = 1;
  private conversationId = crypto.randomUUID();

  readonly messages = signal<ChatMessage[]>([]);
  readonly busy = signal(false);
  readonly panelOpen = signal(false);
  /** True while the Ask page is showing the thread. */
  readonly pageVisible = signal(false);
  /** Answers that arrived while the chat was closed. */
  readonly unread = signal(0);
  readonly live = isLive('ask');
  /** False after a question failed, until the next one gets through. */
  readonly reachable = signal(true);

  constructor() {
    this.router.events.pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd)).subscribe((event) => {
      const url = event.urlAfterRedirects;
      const path = url.split(/[?#]/)[0];
      if (path === '/ask') {
        this.closePanel();
      } else {
        this.returnUrl = url;
        if (this.previousPath === '/ask' && (this.messages().length || this.busy())) {
          this.panelOpen.set(innerWidth >= 900);
        } else if (innerWidth < 900) {
          this.closePanel();
        }
      }
      this.previousPath = path;
    });
  }

  expand(): void {
    if (this.router.url.split(/[?#]/)[0] !== '/ask') this.returnUrl = this.router.url;
    void this.router.navigateByUrl('/ask');
  }

  returnToPanel(): void {
    void this.router.navigateByUrl(this.returnUrl, { replaceUrl: true }).then((navigated) => {
      if (navigated) this.openPanel();
    });
  }

  openPanel(question?: string): void {
    this.panelOpen.set(true);
    this.unread.set(0);
    if (question) this.send(question);
  }

  /** Asks from anywhere: on the Ask page the answer appears there, elsewhere the chat panel opens. */
  ask(question: string): void {
    if (this.pageVisible()) this.send(question);
    else this.openPanel(question);
  }

  closePanel(): void {
    this.panelOpen.set(false);
  }

  togglePanel(): void {
    if (this.panelOpen()) this.closePanel();
    else this.openPanel();
  }

  send(text: string): boolean {
    const question = text.trim();
    if (!question || this.busy()) return false;
    this.busy.set(true);

    const replyId = this.nextId + 1;
    this.messages.update((list) => [
      ...list,
      { id: this.nextId, role: 'user', text: question },
      { id: replyId, role: 'assistant', steps: [] },
    ]);
    this.nextId += 2;

    this.sub = this.api.ask(question, this.conversationId).subscribe({
      next: (event) => {
        this.reachable.set(true);
        this.patch(replyId, (m) => (event.type === 'step' ? { ...m, steps: [...(m.steps ?? []), event.step] } : { ...m, answer: event.answer }));
      },
      error: (e: Error) => {
        this.reachable.set(false);
        this.patch(replyId, (m) => ({ ...m, text: e?.message || 'Sorry, something went wrong. Please try again.' }));
        this.finish();
      },
      complete: () => this.finish(),
    });
    return true;
  }

  clear(): void {
    this.conversationId = crypto.randomUUID();
    this.sub?.unsubscribe();
    this.busy.set(false);
    this.messages.set([]);
    this.unread.set(0);
  }

  private finish(): void {
    this.busy.set(false);
    if (!this.panelOpen() && !this.pageVisible()) this.unread.update((n) => n + 1);
  }

  private patch(id: number, fn: (m: ChatMessage) => ChatMessage): void {
    this.messages.update((list) => list.map((m) => (m.id === id ? fn(m) : m)));
  }
}
