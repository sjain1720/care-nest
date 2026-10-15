import { Component, DestroyRef, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize, skip } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { ApiService, isLive } from '../services/api.service';
import { TreatmentPlanPreparation } from '../models/models';
import { CitationChipComponent } from './citation-chip.component';
import { InrPipe } from './inr.pipe';

@Component({
  selector: 'app-treatment-planning', standalone: true,
  imports: [MatButtonModule, DatePipe, CitationChipComponent, InrPipe],
  template: `@if (live) {
    <section class="card" id="treatment-planning" aria-labelledby="treatment-planning-title">
      <h2 id="treatment-planning-title">Before a planned admission</h2>
      <p class="small muted">Compare recorded waiting-period dates and a normal-room quote, then see what to confirm. These checks do not establish coverage or cashless approval.</p>
      <div class="inputs">
        <label>Procedure you are planning<input maxlength="200" [value]="procedure()" (input)="procedure.set($any($event.target).value)" placeholder="For example, cataract surgery" /></label>
        <label>Planned admission date (optional)<input type="date" [value]="plannedDate()" (input)="plannedDate.set($any($event.target).value)" /></label>
        <label>Normal-room price per day (optional)<input type="number" min="1" max="1000000" [value]="roomRate()" (input)="roomRate.set($any($event.target).value)" /></label>
      </div>
      <button mat-flat-button type="button" [disabled]="busy() || procedure().trim().length < 2" (click)="check()">{{ busy() ? 'Checking…' : 'Check dates and room quote' }}</button>
      @if (error()) { <p role="alert">{{ error() }}</p> }
      @if (result(); as plan) {
        @for (warning of plan.warnings; track $index) { <p class="small muted">{{ warning }}</p> }
        @for (wait of plan.waitingPeriods; track $index) {
          <div class="wait">
            <strong>{{ wait.label }}</strong> · {{ wait.appliesTo }}
            <p>{{ statuses[wait.dateStatus] }} @if (wait.endDate) { · Recorded end: {{ wait.endDate | date:'d MMM y' }} }
              @if (wait.daysRemainingAtAdmission !== null && wait.daysRemainingAtAdmission > 0) { · {{ wait.daysRemainingAtAdmission }} days still remaining at admission }</p>
            @if (wait.citation) { <app-citation-chip [citation]="wait.citation" /> }
          </div>
        }
        @if (plan.roomRisk; as risk) {
          <p><strong>Recorded normal-room limit:</strong> {{ risk.recordedLimitPerDay | inr }}/day.
            <strong>Your quote:</strong> {{ risk.proposedRatePerDay | inr }}/day.</p>
          <p>{{ risk.status === 'above_recorded_limit' ? 'Above the recorded limit' : 'Within the recorded limit' }}.
            Daily room-price excess: {{ risk.dailyExcess | inr }}. This is not a total out-of-pocket estimate.</p>
          @if (risk.citation) { <app-citation-chip [citation]="risk.citation" /> }
        }
        @if (plan.coPay) { <p><strong>Recorded co-pay:</strong> {{ plan.coPay.label }}. Confirm applicability to the member.</p> }
        @if (plan.deductible) { <p><strong>Recorded deductible:</strong> {{ plan.deductible.label }}</p> }
        <h3>Questions before admission</h3>
        <ul>@for (question of plan.questionsToConfirm; track $index) { <li>{{ question }}</li> }</ul>
      }
    </section>
  }`,
  styles: `.inputs { display:grid; gap:12px; margin:12px 0; } input { display:block; width:100%; box-sizing:border-box; padding:10px; font:inherit; color:var(--cn-ink); background:var(--cn-surface); border:1px solid var(--cn-border); border-radius:8px; } .wait { padding:12px 0; border-bottom:1px solid var(--cn-border); } @media(min-width:900px) { .inputs { grid-template-columns:repeat(3,minmax(0,1fr)); } }`,
})
export class TreatmentPlanningComponent {
  private api = inject(ApiService);
  private destroy = inject(DestroyRef);
  readonly live = isLive('policy');
  readonly procedure = signal(''); readonly plannedDate = signal(''); readonly roomRate = signal('');
  readonly busy = signal(false); readonly error = signal<string | null>(null);
  readonly result = signal<TreatmentPlanPreparation | null>(null);
  readonly statuses = {ends_by_planned_date:'Recorded waiting-period end is on or before this date; applicability needs confirmation',
    running_on_planned_date:'Recorded waiting period is still running on this date',
    end_date_unknown:'Waiting-period end date is unknown', planned_date_missing:'Add a planned date to compare'};
  constructor() {
    this.api.getPolicy().pipe(skip(1), takeUntilDestroyed(this.destroy)).subscribe(() => this.result.set(null));
  }
  check(): void {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(null); this.result.set(null);
    this.api.prepareTreatmentPlan({procedure:this.procedure().trim(),
      ...(this.plannedDate() ? {plannedAdmission:this.plannedDate()} : {}),
      ...(this.roomRate() ? {normalRoomRatePerDay:Number(this.roomRate())} : {})})
      .pipe(takeUntilDestroyed(this.destroy), finalize(() => this.busy.set(false)))
      .subscribe({next: result => this.result.set(result), error: () => this.error.set('The check could not complete. Confirm the inputs and try again.')});
  }
}
