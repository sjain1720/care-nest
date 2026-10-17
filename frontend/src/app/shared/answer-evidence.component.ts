import { Component, inject, input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AnswerVerification, Citation } from '../models/models';
import { CitationChipComponent } from './citation-chip.component';
import { ChatService } from '../services/chat.service';

/** Displays server-issued checks; citation count/progress messages cannot mint a pass. */
@Component({
  selector: 'app-answer-evidence',
  standalone: true,
  imports: [DatePipe, FormsModule, MatButtonModule, MatIconModule, CitationChipComponent],
  template: `
    <section class="proof" aria-label="Answer evidence and checks">
      <h4>{{ hasEvidence() ? (verification().scope === 'timing_only' ? 'What we checked · timing only' : 'What we checked') : 'One more policy detail is needed' }}</h4>
      @if (hasEvidence()) {
      <ul class="checks" aria-label="Completed and missing checks">
        @for (check of compactChecks(); track check.kind) {
          <li [class.passed]="check.status === 'passed'" [class.unconfirmed]="check.status === 'not_confirmed'">
            <mat-icon aria-hidden="true">{{ check.status === 'passed' ? 'check_circle' : check.status === 'not_run' ? 'radio_button_unchecked' : 'help_outline' }}</mat-icon>
            {{ check.label }}
          </li>
        }
      </ul>
      } @else { <p class="qualification">The available information does not yet support a reliable answer. Add the relevant policy pages or issued schedule, or ask the insurer to clarify the benefit.</p> }
      @if (verification().dates.length) {
        <p class="qualification">{{ verification().dates[0].startDateOrigin }}.</p>
      }
      @if (needsTreatmentDate()) {
        <form class="date-input" (ngSubmit)="sendDate()">
          <label [for]="dateInputId">Planned treatment date</label>
          <div class="date-controls">
            <input type="date" [id]="dateInputId" name="plannedDate" [(ngModel)]="plannedDate" required />
            <button mat-stroked-button type="submit" [disabled]="!plannedDate || chat.busy()">Check this date</button>
          </div>
          <small>Choose a date to continue this conversation.</small>
        </form>
      }
      <details>
        <summary>See policy evidence and inputs</summary>
        <p class="policy-name">Selected policy: <strong>{{ verification().policyName }}</strong></p>
        @for (citation of citations(); track $index) {
          <div class="source">
            <app-citation-chip [citation]="citation" />
            <blockquote>{{ citation.quote }}</blockquote>
          </div>
        }
        @for (calculation of verification().dates; track calculation.periodId) {
          <section class="date-check" aria-label="Waiting-period date calculation">
            <h5>{{ calculation.label }} · {{ calculation.duration }}</h5>
            <dl>
              <div><dt>Start used</dt><dd>{{ calculation.startDate | date:'d MMM y' }}</dd></div>
              <div><dt>Waiting period ends</dt><dd>{{ calculation.endDate | date:'d MMM y' }}</dd></div>
              <div><dt>Date compared</dt><dd>{{ calculation.comparisonDate | date:'d MMM y' }}</dd></div>
              <div><dt>Timing result</dt><dd>{{ calculation.periodEnded ? 'This period has ended' : 'Still running' }}@if (!calculation.periodEnded) { · {{ calculation.daysRemaining }} days remaining }</dd></div>
            </dl>
          </section>
        }
        @if (hasEvidence()) { <details class="check-method">
          <summary>How these checks work</summary>
          <dl class="check-details">
          @for (check of verification().checks; track check.kind) {
            <div><dt>{{ check.label }}</dt><dd>{{ check.detail }}</dd></div>
          }
          </dl>
        </details> }
        @if (verification().missingInputs.length) {
          <p><strong>Still needed:</strong> {{ verification().missingInputs.join(' ') }}</p>
        }
        @if (hasEvidence()) { <p class="qualification">{{ verification().qualification }}</p> }
      </details>
    </section>
  `,
  styles: `
    :host { display:block; min-width:0; }
    .proof { border:1px solid var(--cn-border); border-radius:12px; padding:12px; margin:8px 0 14px; overflow-wrap:anywhere; }
    h4 { margin:0 0 8px; font-size:.9rem; color:var(--cn-strong); }
    .checks { list-style:none; display:flex; flex-wrap:wrap; gap:6px 12px; padding:0; margin:0 0 10px; }
    .checks li { display:flex; align-items:center; gap:5px; font-size:.78rem; color:var(--cn-muted); }
    .checks .passed { color:var(--cn-primary); }.checks .unconfirmed { color:var(--cn-warn); }
    .checks mat-icon { font-size:17px; width:17px; height:17px; flex:none; }
    summary { cursor:pointer; font-size:.85rem; font-weight:600; padding:5px 0; min-height:24px; }
    summary:focus-visible { outline:2px solid var(--cn-primary); outline-offset:3px; }
    .policy-name { font-size:.85rem; margin:10px 0; }
    blockquote { margin:8px 0 12px; padding:8px 10px; border-left:3px solid var(--cn-primary); background:var(--cn-bg); font-size:.88rem; line-height:1.55; }
    .date-check { border-top:1px solid var(--cn-border); margin-top:12px; padding-top:8px; }
    h5 { margin:5px 0 10px; font-size:.9rem; }
    dl { margin:8px 0; font-size:.83rem; } .date-check dl { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
    dt { color:var(--cn-muted); } dd { margin:3px 0 0; }.date-check dd { font-weight:600; }
    .date-check p, .check-details, details > p { font-size:.8rem; line-height:1.5; }
    .check-details > div { padding:6px 0; }.check-details dt { font-weight:600; }
    .qualification { font-size:.75rem; line-height:1.45; color:var(--cn-muted); margin:8px 0 0; }
    .check-method { border-top:1px solid var(--cn-border); margin-top:10px; }
    .date-input { margin:10px 0; }.date-input label { display:block; font-size:.85rem; font-weight:600; margin-bottom:5px; }
    .date-controls { display:flex; flex-wrap:wrap; gap:8px; }.date-controls input { min-width:0; flex:1; max-width:230px; min-height:44px; box-sizing:border-box; padding:8px; border:1px solid var(--cn-border); border-radius:8px; background:var(--cn-bg); color:var(--cn-strong); font:inherit; }
    .date-input small { display:block; margin-top:4px; color:var(--cn-muted); }
  `,
})
export class AnswerEvidenceComponent {
  readonly chat = inject(ChatService);
  verification = input.required<AnswerVerification>();
  citations = input<Citation[]>([]);
  readonly dateInputId = 'treatment-date-' + crypto.randomUUID();
  plannedDate = '';
  hasEvidence(): boolean { return this.verification().checks.some(c => c.kind === 'quote' && c.status === 'passed'); }
  compactChecks() {
    const checks = this.verification().checks;
    const paired = ['source', 'quote'].every(kind => checks.some(c => c.kind === kind && c.status === 'passed'));
    return checks.filter(c => (c.status === 'passed' || c.kind === 'dates') && !(paired && c.kind === 'quote'))
      .map(c => paired && c.kind === 'source' ? { ...c, label: 'Source and quotation matched' } : c);
  }
  needsTreatmentDate(): boolean { return this.verification().missingInputs.some(text => text.includes('planned treatment date')); }
  sendDate(): void {
    if (this.plannedDate && this.chat.send(`My planned treatment date is ${this.plannedDate}. Please recheck the waiting-period timing.`)) this.plannedDate = '';
  }
}
