import { Component, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { GlossComponent } from './gloss.component';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AnswerCard } from '../models/models';
import { VerdictBadgeComponent } from './verdict-badge.component';
import { CitationChipComponent } from './citation-chip.component';
import { InrPipe } from './inr.pipe';
import { TranslatePipe } from './translate.pipe';

/** Structured answer: verdict first, then plain-English summary, sources, things to confirm and the next step. */
@Component({
  selector: 'app-answer-card',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule, VerdictBadgeComponent, CitationChipComponent, GlossComponent, TranslatePipe, InrPipe],
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

      @if (answer().investigation; as review) {
        <section class="investigation-result" aria-label="Claim investigation result">
          <header class="review-status"><mat-icon>{{ review.status === 'reviewed' ? 'fact_check' : 'info_outline' }}</mat-icon><div><strong>{{ review.status === 'reviewed' ? 'Investigation complete · review the findings' : review.status === 'needs_inputs' ? 'More information needed' : review.status === 'stale' ? 'Documents changed · investigate again' : 'Investigation could not finish' }}</strong><small>Findings depend on the available documents. They do not confirm claim approval.</small></div></header>
          <h4 class="review-heading">1. Check the amounts and documents</h4>
          @if (review.preparation.reconciliation; as amounts) {
            <dl class="review-amounts"><div><dt>Claimed</dt><dd>{{ amounts.claimedAmount | inr }}</dd></div><div><dt>Approved</dt><dd>{{ amounts.approvedAmount | inr }}</dd></div><div><dt>Difference</dt><dd>{{ amounts.decisionDifference | inr }}</dd></div></dl>
            <p class="reconciliation-note"><mat-icon>calculate</mat-icon>{{ amounts.arithmeticOk ? 'Amounts reconcile with the itemized deductions.' : 'The amounts do not reconcile.' }} Itemized: {{ amounts.itemizedDeductions | inr }}.@if (!amounts.arithmeticOk) { <strong>Unexplained gap: {{ amounts.unexplainedGap | inr }}.</strong> }</p>
          }
          @if (review.preparation.missingInputs.length) { <div class="confirm"><strong>What we still need</strong><ul>@for (missing of review.preparation.missingInputs; track missing.code) { <li>{{ missing.message }} <a [routerLink]="missing.route" (click)="actionSelected.emit()">Add or review</a></li> }</ul></div> }
          @if (review.status === 'reviewed') {
          <h4 class="review-heading">2. Examine each reason against the evidence</h4>
          @for (row of review.rows; track row.id) {
            <section class="finding">
              <h4>{{ row.label }} @if (row.amount !== null) { · {{ row.amount | inr }} }</h4>
              <span class="finding-status">{{ row.assessment === 'related_wording' ? 'Related policy wording found' : row.assessment === 'no_stated_reason' ? 'Insurer has not stated a reason' : row.assessment === 'needs_information' ? 'More facts needed' : 'Evidence not verified' }}</span>
              <details><summary>Recorded reason and source evidence</summary><p><strong>Insurer's recorded reason:</strong> {{ row.insurerReason }}</p>
              </details><p>{{ row.explanation }}</p>
              <div class="row sources">@for (citation of row.citations; track $index) { <app-citation-chip [citation]="citation" /> }</div>

            </section>
          } @empty { <p class="muted">No deduction findings are available yet. Review the missing information above or retry the investigation.</p> }
          <h4 class="review-heading">3. Prepare your response</h4>
          @if (review.actions.length) {
            <details class="confirm"><summary>Your clarification checklist ({{ review.actions.length }})</summary>
              <ol>@for (action of review.actions; track $index) { <li><strong>{{ action.question }}</strong><br>Ask {{ action.source }}.<br><span>{{ action.why }}</span></li> }</ol>
              <small>Suggested clarification evidence; these are not confirmed insurer requirements.</small>
            </details>
          }
          @if (review.status === 'reviewed') { <p class="small muted">Open the letter below, review its evidence and fill in any placeholders before sending it yourself.</p> }
          }
        </section>
        @for (warning of review.warnings; track $index) { <p class="small muted">{{ warning }}</p> }
        @if (review.metrics['totalTokens']) {
          <details><summary>Investigation execution</summary>
            <p>ADK · {{ review.metrics['modelCalls'] }} model responses · {{ review.metrics['toolCalls'] }} tool calls ·
              {{ review.metrics['totalTokens'] }} reported tokens · {{ review.metrics['elapsedSeconds'] }} seconds.</p>
            @if (review.metrics['estimatedInferenceUsd'] !== null) { <p>Estimated investigation inference: USD {{ review.metrics['estimatedInferenceUsd'] }}. Excludes ingestion, embeddings, infrastructure and thread routing.</p> }
          </details>
        }
      }

      <div class="row actions">
        @if (answer().nextAction; as next) {
          <a mat-flat-button [routerLink]="next.route" (click)="actionSelected.emit()">{{ next.label | t }} <mat-icon iconPositionEnd>arrow_forward</mat-icon></a>
        }
        @if (answer().secondaryAction; as alt) {
          <a mat-stroked-button class="btn-violet" [routerLink]="alt.route" (click)="actionSelected.emit()">{{ alt.label | t }}</a>
        }
      </div>
    </article>
  `,
  styles: `
    .general { display: inline-flex; align-items: center; gap: 4px; margin-left: 6px; padding: 2px 10px 2px 6px; border-radius: 999px;
               font-size: .78rem; font-weight: 600; background: var(--cn-c2-soft); color: var(--cn-c2-ink); vertical-align: middle; }
    .general mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .review-status { display:flex;gap:10px;align-items:flex-start;background:var(--cn-green-soft);padding:14px;border-radius:12px;margin:16px 0; }
    .review-status mat-icon { color:var(--cn-primary);flex:none; }.review-status small { display:block;color:var(--cn-muted);margin-top:5px;line-height:1.5; }
    .review-heading { font-size:1rem;margin:22px 0 12px;color:var(--cn-strong); }.review-amounts { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0 0 12px; }.review-amounts div { padding:12px 8px;background:var(--cn-bg);border-radius:10px;min-width:0; }.review-amounts dt { color:var(--cn-muted);font-size:.78rem; }.review-amounts dd { margin:6px 0 0;font-weight:700;overflow-wrap:anywhere; }.reconciliation-note { font-size:.85rem; }.reconciliation-note mat-icon { vertical-align:middle;margin-right:5px; }.finding-status { display:inline-block;font-size:.75rem;padding:4px 8px;border-radius:8px;background:var(--cn-warn-soft);color:var(--cn-warn);margin-bottom:10px; }.finding-missing { font-size:.86rem;background:var(--cn-bg);padding:10px;border-radius:10px; }.finding-missing ul { padding-left:18px; }.confirm ol { padding-left:20px; }.confirm ol li { margin:12px 0; }
    .finding { border-top: 1px solid var(--cn-border); padding: 10px 0; }
    .finding h4 { margin: 0 0 8px; }
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
  actionSelected = output<void>();
}
