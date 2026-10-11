import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AnswerCard } from '../models/models';
import { VerdictBadgeComponent } from './verdict-badge.component';
import { CitationChipComponent } from './citation-chip.component';

/** Structured answer: verdict first, then plain-English summary, sources, things to confirm and the next step. */
@Component({
  selector: 'app-answer-card',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule, VerdictBadgeComponent, CitationChipComponent],
  template: `
    <article class="answer">
      <app-verdict-badge [verdict]="answer().verdict" />
      <h3 class="headline">{{ answer().headline }}</h3>
      <p>{{ answer().summary }}</p>

      @if (answer().citations.length) {
        <div class="row sources" aria-label="Sources">
          @for (c of answer().citations; track $index) {
            <app-citation-chip [citation]="c" />
          }
        </div>
      }

      @if (answer().toConfirm.length) {
        <div class="confirm">
          <div class="confirm-title"><mat-icon class="icon-sm">fact_check</mat-icon> Confirm with your insurer or hospital</div>
          <ul>
            @for (item of answer().toConfirm; track $index) {
              <li>{{ item }}</li>
            }
          </ul>
        </div>
      }

      @if (answer().nextAction; as next) {
        <a mat-flat-button [routerLink]="next.route">{{ next.label }} <mat-icon iconPositionEnd>arrow_forward</mat-icon></a>
      }
    </article>
  `,
  styles: `
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
