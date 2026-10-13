import { Component, DestroyRef, ElementRef, HostListener, computed, effect, inject, input, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { MatAutocompleteModule, MatAutocompleteSelectedEvent, MatAutocompleteTrigger } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { filter, map } from 'rxjs';
import { ChatService, chatContext } from '../services/chat.service';
import { SearchItem, SearchService } from '../services/search.service';
import { ChatThreadComponent } from './chat-thread.component';
import { TranslatePipe } from './translate.pipe';

const PLACEHOLDER_TOPICS = ['health policy', 'bill claim preparations', 'explain rejected claim', 'waiting periods for diseases'];

/**
 * One bar at the bottom of every page for asking AND finding (like ChatGPT/Gemini).
 * Typing shows places and facts to jump to; Enter asks the assistant. Answers open in a sheet above the bar.
 */
@Component({
  selector: 'app-chat-bar',
  standalone: true,
  imports: [FormsModule, RouterLink, MatAutocompleteModule, MatButtonModule, MatIconModule, ChatThreadComponent, TranslatePipe],
  template: `
    @if (!inline() && chat.panelOpen() && !onAskPage()) {
      <section class="sheet" role="dialog" aria-modal="false" aria-labelledby="chat-title">
        <header class="sheet-head">
          <span class="avatar" aria-hidden="true"><mat-icon>auto_awesome</mat-icon></span>
          <div class="titles">
            <h2 id="chat-title">{{ 'Nessi' | t }}</h2>
            <span [class]="'state ' + (!chat.live ? 'demo' : chat.reachable() ? 'on' : 'off')">{{ (!chat.live ? 'Demo: answers from the sample claim' : chat.reachable() ? 'General guidance or answers from your selected documents' : "Can't reach CareNest right now") | t }}</span>
          </div>
          @if (chat.messages().length) {
            <button mat-icon-button type="button" (click)="chat.clear()" aria-label="Start a new chat" title="New chat"><mat-icon>add_comment</mat-icon></button>
          }
          <a mat-icon-button class="full-page" routerLink="/ask" aria-label="Open the chat as a full page" title="Full page"><mat-icon>open_in_full</mat-icon></a>
          <button mat-icon-button type="button" (click)="close()" aria-label="Close the chat" title="Close"><mat-icon>expand_more</mat-icon></button>
        </header>
        <div class="sheet-body">
          <app-chat-thread [prompts]="context().prompts" [compact]="true" (pick)="ask($event)" />
        </div>
      </section>
    }

    <div class="dock no-print" [class.inline]="inline()" [class.with-side]="!inline() && chat.panelOpen() && !onAskPage()" [class.away]="!inline() && !docked()">
      <form class="bar" [class.busy]="chat.busy()" [class.unread]="chat.unread() > 0" matAutocompleteOrigin #origin="matAutocompleteOrigin"
            (ngSubmit)="submit()" role="search">
        <span class="spark" aria-hidden="true"><mat-icon>auto_awesome</mat-icon></span>
        <label [attr.for]="inputId()" class="sr-only">{{ 'Ask CareNest a question, or find something' | t }}</label>
        <span class="field">
          <input #box [id]="inputId()" name="q" autocomplete="off" spellcheck="false" enterkeyhint="send"
                 [ngModel]="query()" (ngModelChange)="query.set($event)" (focus)="search.refresh()"
                 [matAutocomplete]="auto" [matAutocompleteConnectedTo]="origin" [matAutocompletePosition]="(phone() && !chat.panelOpen()) || inline() ? 'below' : 'above'">
          @if (!query()) {
            <span class="ph" aria-hidden="true">{{ 'Ask CareNest about your' | t }}
              <!-- Each case is a new element, so the fade-in replays on every change. -->
              @switch (topic()) {
                @case (0) { <span class="ph-topic">{{ topics[0] | t }}</span> }
                @case (1) { <span class="ph-topic">{{ topics[1] | t }}</span> }
                @case (2) { <span class="ph-topic">{{ topics[2] | t }}</span> }
                @default { <span class="ph-topic">{{ topics[3] | t }}</span> }
              }</span>
          }
        </span>
        @if (!inline() && !onAskPage() && chat.messages().length && !chat.panelOpen()) {
          <button type="button" class="open-chat" (click)="chat.openPanel()" [attr.aria-label]="chat.unread() ? 'Open chat, new answer' : 'Open chat'">
            <mat-icon>forum</mat-icon><span class="open-label">{{ (chat.unread() ? 'New answer' : 'Chat') | t }}</span>
          </button>
        }
        <button type="submit" class="send" [disabled]="!query().trim() || chat.busy()" [attr.aria-label]="'Ask' | t">
          <mat-icon>{{ chat.busy() ? 'more_horiz' : 'arrow_upward' }}</mat-icon>
        </button>
      </form>
      @if (!inline()) {
        <p class="hint">{{ 'Ask in your own words, or type to find a page. Press / to start typing.' | t }}</p>
      }
    </div>

    <mat-autocomplete #auto="matAutocomplete" class="cn-search-panel" [autoActiveFirstOption]="!!query().trim()" [displayWith]="blank"
                      [panelWidth]="inline() || phone() || (chat.panelOpen() && !onAskPage()) ? '' : 560" (optionSelected)="pick($event)">
      @for (g of results(); track g.group) {
        <mat-optgroup [label]="(g.group === 'Ask CareNest' ? (query().trim() ? 'Ask CareNest' : 'Try asking') : g.group) | t">
          @for (item of g.items; track item.label + (item.fragment ?? '')) {
            <mat-option [value]="item">
              <span class="opt">
                <mat-icon class="opt-icon" [class.ask]="!!item.ask">{{ item.icon }}</mat-icon>
                <span class="opt-text">
                  <span class="opt-label">{{ item.label }}</span>
                  @if (item.hint) { <span class="opt-hint">{{ item.hint }}</span> }
                </span>
              </span>
            </mat-option>
          }
        </mat-optgroup>
      }
    </mat-autocomplete>
  `,
  styles: `
    .dock { position: fixed; z-index: 34; left: var(--cn-side-w, 0px); right: 0; bottom: 0; padding: 0 16px 10px;
            display: flex; flex-direction: column; align-items: center; pointer-events: none;
            background: linear-gradient(to top, var(--cn-bg) 55%, transparent); view-transition-name: chat-bar; }
    .bar { pointer-events: auto; position: relative; width: min(780px, 100%); display: flex; align-items: center; gap: 6px;
           min-height: 58px; padding: 6px 6px 6px 8px; border-radius: 29px; background: var(--cn-surface);
           border: 1.5px solid transparent;
           background-image: linear-gradient(var(--cn-surface), var(--cn-surface)), var(--cn-search-edge);
           background-origin: border-box; background-clip: padding-box, border-box;
           box-shadow: 0 0 0 4px rgba(34, 197, 94, .10), 0 10px 30px rgba(15, 44, 89, .25), 0 0 28px rgba(34, 197, 94, .18);
           transition: box-shadow .2s, transform .2s var(--cn-ease); }
    .bar:hover, .bar:focus-within { box-shadow: 0 0 0 4px rgba(34, 197, 94, .22), 0 12px 34px rgba(15, 44, 89, .3), 0 0 36px rgba(34, 197, 94, .32); }
    .bar:focus-within { transform: translateY(-1px); }
    .spark { width: 40px; height: 40px; flex: none; border-radius: 50%; display: grid; place-items: center;
             background: linear-gradient(135deg, var(--cn-navy), var(--cn-navy-700)); color: var(--cn-search-icon); }
    .field { position: relative; flex: 1; min-width: 0; display: flex; align-items: center; }
    input { flex: 1; min-width: 0; height: 44px; border: 0; background: none; padding: 0 6px; font: inherit; font-size: 1rem; color: var(--cn-ink); }
    input:focus { outline: none; }
    .ph { position: absolute; left: 6px; right: 6px; top: 50%; transform: translateY(-50%); pointer-events: none;
          color: var(--cn-muted); font-size: 1rem; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ph-topic { color: var(--cn-green-strong); font-weight: 600; }
    .send { width: 44px; height: 44px; flex: none; border: 0; border-radius: 50%; display: grid; place-items: center; cursor: pointer;
            background: var(--cn-send-bg); color: var(--cn-send-ink); transition: transform .15s, background .15s, opacity .15s; }
    .send:hover:not(:disabled) { transform: scale(1.06); filter: brightness(1.08); }
    .send:disabled { opacity: .45; cursor: default; }
    .open-chat { display: inline-flex; align-items: center; gap: 4px; height: 36px; padding: 0 12px; flex: none; border-radius: 18px; cursor: pointer;
                 border: 1px solid var(--cn-border-strong); background: var(--cn-surface); color: var(--cn-link); font: inherit; font-size: .8rem; font-weight: 600; }
    .bar.unread .open-chat { background: var(--cn-green); color: var(--cn-navy-900); border-color: var(--cn-green); }
    .hint { pointer-events: auto; margin: 6px 0 0; font-size: .76rem; color: var(--cn-muted); text-align: center; }
    kbd { padding: 0 5px; border: 1px solid var(--cn-border-strong); border-radius: 4px; font: inherit; }
    /* Wide screens: no bar at the bottom of every page; it shows with the open chat and on the Ask page. */
    .dock.away { display: none; }
    /* Inline (dashboard banner): sits in the page flow instead of being fixed to the screen. */
    .dock.inline { position: static; padding: 0; background: none; align-items: flex-start; view-transition-name: none; animation: none; }
    /* Compact pill with a teal edge inside the banner card. */
    .dock.inline .bar { width: min(560px, 100%); min-height: 44px; gap: 4px; padding: 3px 3px 3px 4px; border-radius: 22px;
                        background: var(--cn-field); border: 2px solid var(--cn-search-line); box-shadow: var(--cn-shadow); }
    .dock.inline .bar:hover, .dock.inline .bar:focus-within { box-shadow: 0 0 0 4px rgba(20, 184, 166, .25), var(--cn-shadow); transform: none; }
    .dock.inline .spark { width: 32px; height: 32px; background: linear-gradient(135deg, var(--cn-navy), var(--cn-navy-700)); color: var(--cn-search-icon); }
    .dock.inline .spark mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .dock.inline input { height: 34px; font-size: .9rem; color: var(--cn-ink); }
    .dock.inline .ph { font-size: .88rem; color: var(--cn-muted); }
    .dock.inline .ph-topic { color: var(--cn-primary); }
    .dock.inline .send { width: 34px; height: 34px; background: var(--cn-search-send-bg); color: var(--cn-search-send-ink); }
    .dock.inline .send:hover:not(:disabled) { background: var(--cn-search-send-hover); }
    .dock.inline .send mat-icon { font-size: 20px; width: 20px; height: 20px; }

    .sheet { position: fixed; z-index: 33; left: calc(var(--cn-side-w, 0px) + 16px); right: 16px; margin: 0 auto;
             width: min(780px, calc(100vw - var(--cn-side-w, 0px) - 32px)); top: calc(var(--cn-topbar-h) + 12px); bottom: 104px;
             display: flex; flex-direction: column; background: var(--cn-surface); border: 1px solid var(--cn-border); border-radius: 20px;
             overflow: hidden; box-shadow: var(--cn-shadow-lg), 0 0 40px rgba(34, 197, 94, .12); }
    /* Assistant header with a status dot: green when live and reachable, grey in the demo, red after a failed question. */
    .sheet-head { display: flex; align-items: center; gap: 6px; padding: 10px 8px 10px 14px; color: var(--cn-strong);
                  background: var(--cn-surface); border-bottom: 1px solid var(--cn-border); }
    .sheet-head a, .sheet-head button { color: var(--cn-muted); }
    .avatar { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; flex: none;
              background: var(--cn-green-soft); color: var(--cn-green-strong); }
    .titles { flex: 1; min-width: 0; line-height: 1.2; }
    .titles h2 { margin: 0; font-size: 1rem; color: var(--cn-strong); }
    .titles span { font-size: .75rem; color: var(--cn-muted); }
    .titles span::before { content: ''; display: inline-block; width: 7px; height: 7px; margin-right: 5px; border-radius: 50%; background: var(--cn-border-strong); vertical-align: 1px; }
    .titles .on::before { background: var(--cn-green-bright); }
    .titles .off::before { background: var(--cn-bad); }
    .sheet-body { flex: 1; overflow-y: auto; padding: 14px; overscroll-behavior: contain; }

    .opt { display: flex; align-items: center; gap: 10px; padding: 1px 0; min-width: 0; }
    .opt-icon { color: var(--cn-link); flex: none; font-size: 20px; width: 20px; height: 20px; margin-right: 0 !important; }
    .opt-icon.ask { color: var(--cn-green-strong); }
    .opt-text { display: flex; flex-direction: column; min-width: 0; line-height: 1.25; }
    .opt-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .opt-hint { font-size: .75rem; color: var(--cn-muted); }

    @media (max-width: 899px) {
      /* Docked under the header, like the search bar in travel apps; the tab bar stays at the bottom. */
      .dock { top: var(--cn-topbar-h); bottom: auto; padding: 8px 12px; background: var(--cn-bg);
              border-bottom: 1px solid var(--cn-border); box-shadow: 0 6px 16px rgba(4, 12, 24, .12); }
      .bar { min-height: 44px; padding: 3px 3px 3px 5px; border-radius: 22px;
             background-image: linear-gradient(var(--cn-field), var(--cn-field)), var(--cn-search-edge);
             box-shadow: none; }
      .bar:hover, .bar:focus-within { box-shadow: 0 0 0 3px rgba(34, 197, 94, .22); transform: none; }
      .spark { width: 30px; height: 30px; }
      .spark mat-icon { font-size: 18px; width: 18px; height: 18px; }
      input { height: 36px; padding: 0 4px; font-size: .95rem; }
      /* Phones: the longer topics wrap to a second line instead of being cut off. */
      .ph { left: 4px; right: 4px; font-size: .82rem; line-height: 1.2; white-space: normal;
            display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
      .send { width: 36px; height: 36px; }
      .send mat-icon { font-size: 20px; width: 20px; height: 20px; }
      .open-chat { width: 36px; height: 36px; padding: 0; justify-content: center; border-radius: 50%; }
      .hint, .open-label, .titles span { display: none; }
      /* The open chat fills the screen, with the typing bar at the bottom like a messaging app (citations still open above it). */
      .sheet { left: 0; right: 0; top: 0; bottom: 0; width: auto; z-index: 38;
               padding-top: env(safe-area-inset-top); padding-bottom: calc(62px + env(safe-area-inset-bottom));
               border-radius: 0; border-width: 0; box-shadow: none; }
      .dock.with-side { top: auto; bottom: 0; z-index: 39; padding: 8px 12px calc(8px + env(safe-area-inset-bottom));
                        background: var(--cn-surface); border-bottom: 0; border-top: 1px solid var(--cn-border); box-shadow: 0 -6px 16px rgba(0, 0, 0, .08); }
      .full-page { display: none !important; }
      .sheet-head { padding: 6px 4px 6px 10px; gap: 2px; }
      .avatar { width: 32px; height: 32px; }
      .titles h2 { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .sheet-head .mat-mdc-icon-button { width: 40px; height: 40px; padding: 8px; --mdc-icon-button-state-layer-size: 40px; }
      .sheet-body { padding: 12px 10px; }
      .opt-label { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.3; }
      .opt-icon { margin-right: 0 !important; }
    }
    @media (max-width: 399px) { .avatar { display: none; } }
    /* Wide screens: the chat is a side panel with the input at its foot, so the page stays visible. */
    @media (min-width: 1200px) {
      .sheet { left: auto; right: 0; margin: 0; width: var(--cn-chat-w); top: var(--cn-topbar-h); bottom: 0; padding-bottom: 92px;
               border-radius: 0; border-width: 0 0 0 1px; }
      .dock.with-side { left: auto; right: 0; width: var(--cn-chat-w); padding: 12px 12px 10px; background: var(--cn-bg); }
      .dock.with-side .hint { display: none; }
      /* The side panel's bar is narrow: the hint wraps to two lines instead of being cut off. */
      .dock.with-side .ph { font-size: .86rem; line-height: 1.25; white-space: normal;
                            display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
    }
    @media print { .sheet, .dock { display: none; } }
    @media (prefers-reduced-motion: no-preference) {
      .dock { animation: cn-rise .5s var(--cn-ease) .1s backwards; }
      .sheet { animation: sheet-in .3s var(--cn-ease) both; transform-origin: bottom center; }
      .bar.busy { animation: thinking 1.6s ease-in-out infinite; }
      .bar.unread .open-chat { animation: nudge 1.4s ease-in-out infinite; }
      .ph-topic { animation: topic-in .2s ease-out; }
    }
    @keyframes topic-in { from { opacity: 0; } to { opacity: 1; } }
    @keyframes sheet-in { from { opacity: 0; transform: translateY(24px) scale(.98); } to { opacity: 1; transform: none; } }
    @keyframes thinking {
      0%, 100% { box-shadow: 0 0 0 4px rgba(34, 197, 94, .12), 0 10px 30px rgba(15, 44, 89, .25), 0 0 20px rgba(34, 197, 94, .2); }
      50% { box-shadow: 0 0 0 6px rgba(34, 197, 94, .3), 0 10px 30px rgba(15, 44, 89, .25), 0 0 44px rgba(34, 197, 94, .45); }
    }
    @keyframes nudge { 0%, 100% { transform: none; } 50% { transform: translateY(-2px); } }
  `,
})
export class ChatBarComponent {
  /** In the page flow (dashboard banner) instead of the bar fixed to the screen. */
  readonly inline = input(false);
  readonly inputId = computed(() => (this.inline() ? 'ask-bar-hero' : 'ask-bar'));
  readonly chat = inject(ChatService);
  readonly search = inject(SearchService);
  private router = inject(Router);
  private box = viewChild.required<ElementRef<HTMLInputElement>>('box');
  private trigger = viewChild.required(MatAutocompleteTrigger);

  private path = toSignal(
    this.router.events.pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd), map((e) => e.urlAfterRedirects.split(/[?#]/)[0])),
    { initialValue: this.router.url.split(/[?#]/)[0] },
  );
  readonly onAskPage = computed(() => this.path() === '/ask');
  readonly context = computed(() => chatContext(this.path()));
  /** Phones and small tablets: the bar sits at the top, under the header. */
  readonly phone = signal(matchMedia('(max-width: 899px)').matches);
  /** The input is shown on phones (under the header), with the open chat, and on the Ask page. */
  readonly docked = computed(() => this.phone() || this.chat.panelOpen() || this.onAskPage());
  readonly topics = PLACEHOLDER_TOPICS;
  readonly topic = signal(0);

  readonly query = signal('');
  readonly results = computed(() => this.search.search(this.query(), this.context().prompts));
  readonly blank = () => '';

  constructor() {
    matchMedia('(max-width: 899px)').addEventListener('change', (e) => this.phone.set(e.matches));
    // Cycle the placeholder topic; stays on the first one for reduced motion.
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const timer = setInterval(() => this.topic.set((this.topic() + 1) % PLACEHOLDER_TOPICS.length), 1600);
      inject(DestroyRef).onDestroy(() => clearInterval(timer));
    }
    effect(() => {
      this.path();
      if (!this.inline() && innerWidth < 900) this.chat.closePanel();
    });
    // Wide screens: the chat's input only appears when it opens, so put the cursor there.
    effect(() => {
      if (!this.inline() && this.chat.panelOpen() && !this.phone()) setTimeout(() => this.box().nativeElement.focus());
    });
  }

  submit(): void {
    this.ask(this.query());
  }

  ask(text: string): void {
    const q = text.trim();
    if (!q || this.chat.busy()) return;
    this.chat.ask(q);
    this.query.set('');
    this.trigger().closePanel();
    // Phones: drop the keyboard so the answer has the whole screen.
    if (innerWidth < 900) this.box().nativeElement.blur();
  }

  pick(event: MatAutocompleteSelectedEvent): void {
    const item = event.option.value as SearchItem;
    if (item.ask) this.ask(item.ask);
    else {
      this.search.open(item);
      this.query.set('');
      this.box().nativeElement.blur();
    }
  }

  close(): void {
    this.chat.closePanel();
    if (this.docked()) this.box().nativeElement.focus();
  }

  @HostListener('document:keydown', ['$event'])
  onKey(e: KeyboardEvent): void {
    if (this.inline()) return;
    const target = e.target instanceof Element ? e.target : null;
    const typing = target?.closest('input, textarea, select, [contenteditable="true"]');
    if ((e.key === '/' && !typing) || (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey))) {
      e.preventDefault();
      const hero = document.getElementById('ask-bar-hero');
      if (this.docked()) this.box().nativeElement.focus();
      else if (hero?.offsetParent) hero.focus();
      else this.chat.openPanel();
    } else if (e.key === 'Escape' && this.chat.panelOpen()) {
      this.close();
    }
  }
}
