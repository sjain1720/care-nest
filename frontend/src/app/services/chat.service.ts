import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Subscription, filter } from 'rxjs';
import { NavigationEnd, Router } from '@angular/router';
import { ApiService, isLive } from './api.service';
import { ChatMessage } from '../models/models';
import { Workspace, WorkspaceService } from './workspace.service';

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
  if (path.startsWith('/dashboard')) return { label: "Ask about the fictional example", prompts: ['What is my room-rent limit?', 'Why was money deducted from my claim?', 'Which documents am I missing?'] };
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

function newThread() {
  return { messages: signal<ChatMessage[]>([]), busy: signal(false), unread: signal(0),
    reachable: signal(true), conversationId: crypto.randomUUID(), sub: undefined as Subscription | undefined };
}
type Thread = ReturnType<typeof newThread>;

/** General and fictional-case threads stay separate; each survives panel/page navigation. */
@Injectable({ providedIn: 'root' })
export class ChatService {
  private api = inject(ApiService);
  private router = inject(Router);
  readonly workspace = inject(WorkspaceService);
  private threads: Record<Workspace, Thread> = { general: newThread(), example: newThread(), personal: newThread() };
  private active = computed(() => this.threads[this.workspace.mode()]);
  private returnUrl = '/';
  private pendingQuestion?: string;
  private pendingOpen = false;
  resumeAfterChoice(): void {
    const question = this.pendingQuestion; this.pendingQuestion = undefined;
    if (this.pendingOpen) { this.pendingOpen = false; this.openPanel(question); }
  }
  cancelChoice(): void { this.pendingQuestion = undefined; this.pendingOpen = false; this.workspace.choosing.set(false); }
  private previousPath = '/';
  private nextId = 1;

  readonly messages = computed(() => this.active().messages());
  readonly busy = computed(() => this.active().busy());
  readonly panelOpen = signal(false);
  /** True while the Ask page is showing the thread. */
  readonly pageVisible = signal(false);
  /** Answers that arrived while the chat was closed. */
  readonly unread = computed(() => this.active().unread());
  get live(): boolean { return this.workspace.mode() !== 'example' || isLive('ask'); }
  /** False after a question failed, until the next one gets through. */
  readonly reachable = computed(() => this.active().reachable());
  readonly contextLabel = computed(() => this.workspace.mode() === 'general' ? 'General insurance guidance' : this.workspace.mode() === 'personal' ? 'Your documents · private guest workspace' : "Your fictional example workspace");

  constructor() {
    effect(() => { this.workspace.mode(); this.panelOpen.set(false); });
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
    void this.router.navigate(['/ask'], { queryParams: { workspace: this.workspace.mode() } });
  }

  returnToPanel(): void {
    void this.router.navigateByUrl(this.returnUrl.startsWith('/ask') ? '/dashboard?workspace=' + this.workspace.mode() : this.returnUrl, { replaceUrl: true }).then((navigated) => {
      if (navigated) this.openPanel();
    });
  }

  openPanel(question?: string): void {
    if (!this.workspace.choice()) { this.pendingQuestion = question; this.pendingOpen = true; this.workspace.choosing.set(true); return; }
    this.panelOpen.set(true);
    this.active().unread.set(0);
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

  markRead(): void { this.active().unread.set(0); }

  togglePanel(): void {
    if (this.panelOpen()) this.closePanel();
    else this.openPanel();
  }

  send(text: string): boolean {
    const question = text.trim();
    if (!question || this.busy()) return false;
    if (!this.workspace.choice()) { this.pendingQuestion = question; this.pendingOpen = true; this.workspace.choosing.set(true); return false; }
    const mode = this.workspace.mode();
    const thread = this.threads[mode];
    thread.busy.set(true);

    const replyId = this.nextId + 1;
    thread.messages.update((list) => [
      ...list,
      { id: this.nextId, role: 'user', text: question },
      { id: replyId, role: 'assistant', steps: [] },
    ]);
    this.nextId += 2;

    thread.sub = this.api.ask(question, thread.conversationId, mode).subscribe({
      next: (event) => {
        thread.reachable.set(true);
        this.patch(thread, replyId, (m) => (event.type === 'step' ? { ...m, steps: [...(m.steps ?? []), event.step] } : { ...m, answer: event.answer }));
      },
      error: (e: Error) => {
        thread.reachable.set(false);
        this.patch(thread, replyId, (m) => ({ ...m, text: e?.message || 'Sorry, something went wrong. Please try again.' }));
        this.finish(thread);
      },
      complete: () => this.finish(thread),
    });
    return true;
  }

  clear(): void {
    const thread = this.active();
    thread.conversationId = crypto.randomUUID();
    thread.sub?.unsubscribe();
    thread.busy.set(false);
    thread.messages.set([]);
    thread.unread.set(0);
  }

  private finish(thread: Thread): void {
    thread.busy.set(false);
    if (this.active() !== thread || (!this.panelOpen() && !this.pageVisible())) thread.unread.update((n) => n + 1);
  }

  private patch(thread: Thread, id: number, fn: (m: ChatMessage) => ChatMessage): void {
    thread.messages.update((list) => list.map((m) => (m.id === id ? fn(m) : m)));
  }
}
