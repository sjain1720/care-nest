import { Component, computed, input, output } from '@angular/core';
import { InrPipe } from './inr.pipe';

export interface WaterfallStep {
  id: string;
  label: string;
  amount: number;
  color: string;
}

interface Column {
  id: string | null;
  label: string;
  amount: number;
  bottom: number;
  height: number;
  color: string;
  isDeduction: boolean;
}

/** Claimed → each deduction → approved, as a waterfall. Plain HTML/CSS so it needs no chart library. */
@Component({
  selector: 'app-waterfall',
  standalone: true,
  imports: [InrPipe],
  template: `
    <div class="chart" role="group" aria-label="From the amount claimed to the amount approved">
      @for (c of columns(); track $index) {
        <div class="col">
          <div class="plot">
            <span class="value" [style.bottom.%]="c.bottom + c.height">{{ c.isDeduction ? '−' : '' }}{{ c.amount | inr }}</span>
            @if (c.isDeduction) {
              <button type="button" class="bar" [class.selected]="selected() === c.id" [style.bottom.%]="c.bottom"
                      [style.height.%]="c.height" [style.background]="c.color" (click)="select.emit(c.id!)"
                      [attr.aria-label]="c.label + ', ' + (c.amount | inr) + ' deducted. Show details.'"></button>
            } @else {
              <div class="bar total" [style.bottom.%]="c.bottom" [style.height.%]="c.height" [style.background]="c.color"></div>
            }
          </div>
          <div class="label">{{ c.label }}</div>
        </div>
      }
    </div>
  `,
  styles: `
    .chart { display: flex; gap: 6px; align-items: stretch; margin: 8px 0; }
    .col { flex: 1; min-width: 0; display: flex; flex-direction: column; }
    .plot { position: relative; height: 200px; border-bottom: 1px solid var(--cn-border); }
    .bar { position: absolute; left: 8%; right: 8%; border: 0; border-radius: 6px 6px 0 0; padding: 0; }
    button.bar { cursor: pointer; border-radius: 4px; }
    button.bar.selected { outline: 3px solid var(--cn-ink); outline-offset: 1px; }
    .value { position: absolute; left: 0; right: 0; text-align: center; font-size: .75rem; font-weight: 700; margin-bottom: 2px;
             font-variant-numeric: tabular-nums; white-space: nowrap; transform: translateY(-2px); }
    .label { font-size: .75rem; text-align: center; color: var(--cn-muted); margin-top: 6px; line-height: 1.2;
             overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
    @media (max-width: 599px) { .plot { height: 160px; } .value { font-size: .65rem; } }
  `,
})
export class WaterfallComponent {
  claimed = input.required<number>();
  approved = input.required<number>();
  steps = input.required<WaterfallStep[]>();
  selected = input<string | null>(null);
  select = output<string>();

  columns = computed<Column[]>(() => {
    const max = Math.max(this.claimed(), 1);
    const pct = (n: number) => (n / max) * 100;
    const cols: Column[] = [{ id: null, label: 'Claimed', amount: this.claimed(), bottom: 0, height: 100, color: '#005cbb', isDeduction: false }];
    let level = this.claimed();
    for (const s of this.steps()) {
      const top = level;
      level -= s.amount;
      // Keep tiny deductions visible and clickable.
      cols.push({ id: s.id, label: s.label, amount: s.amount, bottom: pct(Math.max(level, 0)), height: Math.max(pct(top - Math.max(level, 0)), 2), color: s.color, isDeduction: true });
    }
    cols.push({ id: null, label: 'Approved', amount: this.approved(), bottom: 0, height: pct(this.approved()), color: '#13795b', isDeduction: false });
    return cols;
  });
}
