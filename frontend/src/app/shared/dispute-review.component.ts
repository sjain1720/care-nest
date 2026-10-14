import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { combineLatest, finalize, skip } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { AgentStep, DisputeReview } from '../models/models';
import { ApiService, isLive } from '../services/api.service';
import { AgentProgressComponent } from './agent-progress.component';
import { CitationChipComponent } from './citation-chip.component';
import { InrPipe } from './inr.pipe';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-dispute-review', standalone: true,
  imports: [MatButtonModule, AgentProgressComponent, CitationChipComponent, InrPipe, RouterLink],
  template: `
    @if (live) {
      <section class="card" id="ai-review" aria-labelledby="ai-review-title">
        <h2 id="ai-review-title">Review the decision with the AI team</h2>
        <p class="small muted">Policy evidence, deduction analysis and independent verification. Related wording is not confirmation that a deduction is justified.</p>
        <label for="dispute-clarification">Any clarification from your documents? (optional)</label>
        <textarea id="dispute-clarification" rows="2" maxlength="500" [disabled]="busy()" [value]="clarification()"
          (input)="clarification.set($any($event.target).value)" placeholder="For example: which deduction you want explained, or a date to check."></textarea>
        <button mat-flat-button type="button" [disabled]="busy()" (click)="run()">{{ busy() ? 'Reviewing the sources…' : 'Review my decision' }}</button>
        @if (steps().length) { <app-agent-progress [steps]="steps()" [running]="busy()" /> }
        @if (error()) { <p role="alert">{{ error() }}</p> }
        @if (result(); as review) {
          @if (review.status === 'needs_inputs') {
            <p>Add or confirm these inputs before the specialists can review the evidence:</p>
            <ul>@for (issue of review.preparation.missingInputs; track issue.code) {
              <li>{{ issue.message }} <a [routerLink]="issue.route">Open</a></li>
            }</ul>
          } @else if (review.status === 'stale') {
            <p>The policy or claim changed. Run the review again using the current inputs.</p>
          } @else if (review.status === 'unavailable') {
            <p>The ADK review did not complete. Retry, or use the existing document checks below.</p>
          } @else {
            <p class="small muted">ADK evidence review completed. Review the original documents and unresolved questions before acting.</p>
            @for (row of review.rows; track row.id) {
              <article class="review-row">
                <h3>{{ row.label }} @if (row.amount !== null) { · {{ row.amount | inr }} }</h3>
                <p class="small"><strong>Insurer's stated reason:</strong> {{ row.insurerReason }}</p>
                <span class="pill tone-warn">{{ labels[row.assessment] }}</span>
                <p>{{ row.explanation }}</p>
                <div class="row">@for (citation of row.citations; track $index) { <app-citation-chip [citation]="citation" /> }</div>
                @if (row.missingInformation.length) {
                  <strong>What to confirm</strong>
                  <ul>@for (question of row.missingInformation; track $index) { <li>{{ question }}</li> }</ul>
                }
              </article>
            }
            <a mat-stroked-button routerLink="/case/letter" [queryParams]="{kind: review.preparation.decision === 'rejection' ? 'reconsideration' : 'clarification'}">Open the editable letter</a>
          }
          @for (warning of review.warnings; track $index) { <p class="small muted">{{ warning }}</p> }
        }
      </section>
    }
  `,
  styles: `textarea { display:block; width:100%; box-sizing:border-box; margin:8px 0 12px; padding:10px; font:inherit; color:var(--cn-ink); background:var(--cn-surface); border:1px solid var(--cn-border); border-radius:8px; } .review-row { border-top:1px solid var(--cn-border); padding:12px 0; } app-agent-progress { margin:12px 0; }`,
})
export class DisputeReviewComponent {
  private api = inject(ApiService);
  private destroy = inject(DestroyRef);
  readonly live = isLive('settlement');
  readonly clarification = signal('');
  readonly busy = signal(false);
  readonly steps = signal<AgentStep[]>([]);
  readonly result = signal<DisputeReview | null>(null);
  readonly error = signal<string | null>(null);
  readonly labels = { related_wording: 'Related policy wording; applicability needs confirmation',
    needs_information: 'More information needed', no_stated_reason: 'No clear insurer reason', unverified: 'Explanation could not be verified' };

  constructor() {
    combineLatest([this.api.getPolicy(), this.api.getBill(), this.api.getSettlement(), this.api.getCase()])
      .pipe(skip(1), takeUntilDestroyed(this.destroy)).subscribe(() => this.result.set(null));
  }
  run(): void {
    if (this.busy()) return;
    this.busy.set(true); this.result.set(null); this.error.set(null); this.steps.set([]);
    const question = this.clarification().trim() || 'Explain the deductions or rejection and identify missing evidence.';
    this.api.reviewDispute(question).pipe(takeUntilDestroyed(this.destroy), finalize(() => this.busy.set(false)))
      .subscribe({next: event => {
        if (event.type === 'step') this.steps.update(steps => [...steps, event.step]);
        else this.result.set(event.review);
      }, error: error => this.error.set(error?.message || 'The review could not complete. Please retry.')});
  }
}
