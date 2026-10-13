import { Component, computed, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { ChatService } from '../services/chat.service';
import { GlossComponent } from './gloss.component';
import { TranslatePipe } from './translate.pipe';

export interface NextStep {
  text: string;
  /** Link label, e.g. "Write the letter". */
  action?: string;
  route?: string;
  fragment?: string;
  query?: Record<string, string>;
  /** Question to ask the assistant instead of following a link. */
  ask?: string;
  done?: boolean;
}

/** "What to do now": short numbered steps for the user's situation on this page. */
@Component({
  selector: 'app-next-steps',
  standalone: true,
  imports: [RouterLink, MatIconModule, GlossComponent, TranslatePipe],
  template: `
    @if (steps().length) {
      <section class="card next" [attr.aria-label]="title() | t">
        <h2><mat-icon class="flag">flag</mat-icon>{{ title() | t }}</h2>
        <ol>
          @for (s of visible(); track s.text; let i = $index) {
            <li [class.done]="s.done">
              <span class="num" aria-hidden="true">@if (s.done) { <mat-icon>check</mat-icon> } @else { {{ i + 1 }} }</span>
              <span class="body">
                <span class="text"><app-gloss [text]="s.text | t" />@if (s.done) { <span class="sr-only"> ({{ 'done' | t }})</span> }</span>
                @if (s.route) {
                  <a class="go" [routerLink]="s.route" [fragment]="s.fragment" [queryParams]="s.query">{{ (s.action ?? 'Go') | t }}<mat-icon>arrow_forward</mat-icon></a>
                } @else if (s.ask) {
                  <button type="button" class="go" (click)="chat.ask(s.ask)">{{ (s.action ?? 'Ask') | t }}<mat-icon>auto_awesome</mat-icon></button>
                }
              </span>
            </li>
          }
        </ol>
        @if (steps().length > limit) {
          <button type="button" class="more" (click)="expanded.set(!expanded())" [attr.aria-expanded]="expanded()">
            {{ expanded() ? ('Show fewer' | t) : ('Show all' | t) + ' ' + steps().length }}<mat-icon>{{ expanded() ? 'expand_less' : 'expand_more' }}</mat-icon>
          </button>
        }
      </section>
    }
  `,
  styles: `
    .next { border-left: 4px solid var(--cn-green); }
    h2 { display: flex; align-items: center; gap: 6px; }
    .flag { color: var(--cn-green-strong); }
    ol { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
    li { display: flex; align-items: flex-start; gap: 10px; }
    .num { width: 26px; height: 26px; flex: none; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: .8rem;
           background: var(--cn-tile); color: var(--cn-tile-ink); margin-top: 1px; }
    .num mat-icon { font-size: 16px; width: 16px; height: 16px; }
    li.done .num { background: var(--cn-green); color: var(--cn-navy-900); }
    li.done .text { color: var(--cn-muted); text-decoration: line-through; }
    .body { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
    .text { flex: 1 1 260px; min-width: 0; }
    .go { display: inline-flex; align-items: center; gap: 4px; min-height: 36px; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--cn-border-strong);
          background: var(--cn-surface); color: var(--cn-link); font: inherit; font-size: .85rem; font-weight: 600; text-decoration: none; cursor: pointer;
          transition: box-shadow .2s, border-color .2s; }
    .go mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .more { display: inline-flex; align-items: center; gap: 2px; min-height: 40px; margin-top: 8px; padding: 0 4px; border: 0; background: none;
            color: var(--cn-link); font: inherit; font-size: .875rem; font-weight: 600; cursor: pointer; }
  `,
})
export class NextStepsComponent {
  readonly chat = inject(ChatService);
  steps = input.required<NextStep[]>();
  title = input('What to do now');
  readonly limit = 3;
  readonly expanded = signal(false);
  readonly visible = computed(() => (this.expanded() ? this.steps() : this.steps().slice(0, this.limit)));
}
