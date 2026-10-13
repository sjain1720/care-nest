import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { GlossComponent } from './gloss.component';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AnswerCard } from '../models/models';
import { VerdictBadgeComponent } from './verdict-badge.component';
import { CitationChipComponent } from './citation-chip.component';
import { TranslatePipe } from './translate.pipe';

/** Structured answer: verdict first, then plain-English summary, sources, things to confirm and the next step. */
@Component({
  selector: 'app-answer-card',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule, VerdictBadgeComponent, CitationChipComponent, GlossComponent, TranslatePipe],
  template: `
    <article class="answer">
      <app-verdict-badge [verdict]="answer().verdict" />
      @if (answer().general) {
        <span class="general"><mat-icon>public</mat-icon>{{ 'General information – not from your policy' | t }}</span>
      }
      <h3 class="headline">{{ answer().headline }}</h3>
      <p><app-gloss [text]="answer().summary" /></p>

      @if (answer().citations.length) {
        <div class="row sources" [attr.aria-label]="'Sources' | t">
          @for (c of answer().citations; track $index) {
            <app-citation-chip [citation]="c" />
          }
        </div>
      }

      @if (answer().toConfirm.length) {
        <div class="confirm">
          <div class="confirm-title"><mat-icon class="icon-sm">flag</mat-icon> {{ 'What to do next' | t }}</div>
          <ul>
            @for (item of answer().toConfirm; track $index) {
              <li>{{ item }}</li>
            }
          </ul>
        </div>
      }

      <div class="row actions">
        @if (answer().nextAction; as next) {
          <a mat-flat-button [routerLink]="next.route">{{ next.label | t }} <mat-icon iconPositionEnd>arrow_forward</mat-icon></a>
        }
        @if (answer().secondaryAction; as alt) {
          <a mat-stroked-button class="btn-violet" [routerLink]="alt.route">{{ alt.label | t }}</a>
        }
      </div>
    </article>
  `,
  styles: `
    .general { display: inline-flex; align-items: center; gap: 4px; margin-left: 6px; padding: 2px 10px 2px 6px; border-radius: 999px;
               font-size: .78rem; font-weight: 600; background: var(--cn-c2-soft); color: var(--cn-c2-ink); vertical-align: middle; }
    .general mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .actions { gap: 8px; }
    .headline { margin: 10px 0 4px; font-size: 1.1rem; }
    p { margin: 0 0 12px; }
    .sources { margin-bottom: 12px; }
    .confirm { background: var(--cn-warn-soft); border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; font-size: .9rem; }
    .confirm-title { display: flex; align-items: center; gap: 6px; font-weight: 600; color: var(--cn-warn); }
    .confirm ul { margin: 6px 0 0; padding-left: 20px; }
  `,
})
export class AnswerCardComponent {
  answer = input.required<AnswerCard>();
}
