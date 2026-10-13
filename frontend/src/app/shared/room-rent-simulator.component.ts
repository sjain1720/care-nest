import { Component, computed, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { Citation } from '../models/models';
import { InrPipe } from './inr.pipe';
import { CitationChipComponent } from './citation-chip.component';
import { TranslatePipe } from './translate.pipe';

interface RoomOption {
  label: string;
  rate: number;
}

/** "What if I pick this room?" – shows the proportionate deduction before admission. Pure arithmetic, no AI. */
@Component({
  selector: 'app-room-rent-simulator',
  standalone: true,
  imports: [FormsModule, MatButtonModule, InrPipe, CitationChipComponent, TranslatePipe],
  template: `
    <div class="presets" role="group" [attr.aria-label]="'Room type' | t">
      @for (o of options; track o.label) {
        <button type="button" mat-stroked-button [class.chosen]="rate() === o.rate" (click)="rate.set(o.rate)">
          {{ o.label | t }} · {{ o.rate | inr }}
        </button>
      }
    </div>

    <div class="fields">
      <label>{{ 'Room rate per day (₹)' | t }}
        <input type="number" min="0" step="500" [ngModel]="rate()" (ngModelChange)="rate.set(toNumber($event))">
      </label>
      <label>{{ 'Days in hospital' | t }}
        <input type="number" min="1" max="60" [ngModel]="days()" (ngModelChange)="days.set(toNumber($event))">
      </label>
      <label>{{ 'Doctor + nursing charges (₹)' | t }}
        <input type="number" min="0" step="1000" [ngModel]="associated()" (ngModelChange)="associated.set(toNumber($event))">
      </label>
    </div>

    <div class="result" [class.ok]="!result().over" aria-live="polite">
      @if (result().over) {
        <div class="big">{{ 'You may pay about' | t }} <strong>{{ result().total | inr }}</strong> {{ 'extra' | t }}</div>
        <ul>
          <li>Room rent above your limit: {{ days() }} days × {{ rate() - limit() | inr }} = <strong>{{ result().roomCut | inr }}</strong></li>
          <li>Doctor and nursing cut by {{ result().cutPct }}%: {{ associated() | inr }} × {{ result().cutPct }}% = <strong>{{ result().associatedCut | inr }}</strong></li>
        </ul>
        <p class="small">A room at or below {{ limit() | inr }}/day avoids both cuts.</p>
      } @else {
        <div class="big">{{ 'Within your limit – no room-rent cut' | t }}</div>
        <p class="small">Your policy pays room rent up to {{ limit() | inr }} per day.</p>
      }
    </div>

    <div class="row">
      @for (c of citations(); track $index) { <app-citation-chip [citation]="c" /> }
    </div>
    <p class="muted small">{{ 'Estimate only. Insurers may treat ICU, packages and some charges differently – confirm with the insurer before admission.' | t }}</p>
  `,
  styles: `
    .presets { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .presets .chosen { background: var(--cn-primary-soft); border-color: var(--cn-primary); }
    .fields { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin-bottom: 12px; }
    label { display: flex; flex-direction: column; gap: 4px; font-size: .85rem; color: var(--cn-muted); }
    input { min-height: 44px; padding: 0 12px; font: inherit; font-size: 1rem; color: var(--cn-ink); border: 1px solid var(--cn-border); border-radius: 10px; }
    .result { border-radius: 12px; padding: 12px 16px; margin-bottom: 12px; background: var(--cn-bad-soft); }
    .result.ok { background: var(--cn-ok-soft); }
    .big { font-size: 1.1rem; font-weight: 600; }
    .result ul { margin: 8px 0; padding-left: 20px; }
    .result p { margin: 0; }
  `,
})
export class RoomRentSimulatorComponent {
  limit = input.required<number>();
  citations = input<Citation[]>([]);

  readonly options: RoomOption[] = [
    { label: 'General ward', rate: 2500 },
    { label: 'Twin sharing', rate: 5000 },
    { label: 'Single room', rate: 7500 },
    { label: 'Deluxe', rate: 10000 },
  ];

  // Pre-filled with Kamala's stay so the demo matches the ₹21,600 deduction.
  rate = signal(7500);
  days = signal(4);
  associated = signal(34800);

  result = computed(() => {
    const rate = this.rate();
    const limit = this.limit();
    const over = rate > limit && limit > 0;
    const share = over ? limit / rate : 1;
    const roomCut = over ? this.days() * (rate - limit) : 0;
    const associatedCut = Math.round(this.associated() * (1 - share));
    return { over, roomCut, associatedCut, total: roomCut + associatedCut, cutPct: Math.round((1 - share) * 1000) / 10 };
  });

  toNumber(value: unknown): number {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : 0;
  }
}
