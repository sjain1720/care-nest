import { Component, computed, input, output } from '@angular/core';
import { InrPipe } from './inr.pipe';
import { TranslatePipe } from './translate.pipe';

export interface WaterfallStep {
  id: string;
  label: string;
  /** The insurer's own wording, shown under the plain label. */
  insurerLabel?: string;
  amount: number;
  color: string;
}

/**
 * Paid vs cut in one bar, then each cut drawn as its share of the total cut. Small cuts stay large enough to see and tap.
 * Plain HTML/CSS, no chart library.
 */
@Component({
  selector: 'app-waterfall',
  standalone: true,
  imports: [InrPipe, TranslatePipe],
  template: `
    <div class="split" role="img" [attr.aria-label]="('You claimed' | t) + ' ' + (claimed() | inr) + ', ' + ('Paid' | t) + ' ' + (approved() | inr) + ', ' + ('Cut' | t) + ' ' + (cut() | inr)">
      <span class="paid" [style.width.%]="paidPct()"><span class="in">{{ 'Paid' | t }} {{ approved() | inr }}</span></span>
      <span class="cut"><span class="in">{{ 'Cut' | t }} {{ cut() | inr }}</span></span>
    </div>
    <div class="legend"><span>{{ 'You claimed' | t }} <strong>{{ claimed() | inr }}</strong></span><span>{{ paidPct() }}% {{ 'paid' | t }}</span></div>

    <h3 class="sub">{{ 'Where the' | t }} {{ cut() | inr }} {{ 'cut went' | t }}</h3>
    <div class="chart" role="group" [attr.aria-label]="'Each cut, as a share of the total cut' | t">
      @for (s of rows(); track s.id) {
        <button type="button" class="wf-row" [class.selected]="selected() === s.id" (click)="select.emit(s.id)"
                [attr.aria-pressed]="selected() === s.id"
                [attr.aria-label]="(s.label | t) + ', ' + (s.amount | inr) + ', ' + s.share + '%. ' + ('Show details.' | t)">
          <span class="head">
            <span class="label"><span class="dot" [style.background]="s.color"></span>{{ s.label | t }}</span>
            <span class="value">{{ s.amount | inr }} <small>{{ s.share }}%</small></span>
          </span>
          @if (s.insurerLabel && s.insurerLabel !== s.label) { <span class="insurer">{{ 'Insurer calls it:' | t }} “{{ s.insurerLabel }}”</span> }
          <span class="track"><span class="bar" [style.width.%]="s.share" [style.background]="s.color"></span></span>
        </button>
      }
    </div>
  `,
  styles: `
    .split { display: flex; height: 34px; border-radius: 10px; overflow: hidden; margin: 12px 0 6px; background: var(--cn-track); }
    .split > span { display: flex; align-items: center; min-width: 0; overflow: hidden; font-size: .8rem; font-weight: 700; white-space: nowrap; }
    .paid { background: linear-gradient(90deg, var(--cn-green-strong), var(--cn-green)); color: #052e16; justify-content: flex-start; }
    .cut { flex: 1; background: var(--cn-seg-1); color: #fff; justify-content: flex-end; }
    :host-context(html[data-theme="dark"]) .cut { color: #2a0606; }
    .in { padding: 0 10px; }
    .legend { display: flex; justify-content: space-between; gap: 8px; font-size: .8rem; color: var(--cn-muted); flex-wrap: wrap; }
    .sub { margin: 16px 0 6px; font-size: .95rem; }
    .chart { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
    .wf-row { display: block; width: 100%; padding: 8px 10px; border: 1px solid var(--cn-border); border-radius: 12px; background: var(--cn-surface);
              font: inherit; color: inherit; text-align: left; cursor: pointer; }
    .wf-row.selected { background: var(--cn-primary-soft); border-color: var(--cn-link); box-shadow: inset 0 0 0 1px var(--cn-link); }
    .head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; font-size: .9rem; }
    .label { display: inline-flex; align-items: center; gap: 8px; min-width: 0; font-weight: 600; color: var(--cn-strong); }
    .dot { width: 10px; height: 10px; border-radius: 3px; flex: none; }
    .value { font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; color: var(--cn-bad); }
    .value small { color: var(--cn-muted); font-weight: 600; margin-left: 4px; }
    .insurer { display: block; font-size: .75rem; color: var(--cn-muted); margin: 2px 0 0 18px; }
    .track { display: block; position: relative; height: 12px; margin-top: 6px; background: var(--cn-track); border-radius: 999px; overflow: hidden; }
    .bar { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 999px; min-width: 6px; }
    @media (prefers-reduced-motion: no-preference) {
      .bar, .paid { animation: grow .8s cubic-bezier(.2, .7, .2, 1) .15s backwards; transform-origin: left; }
    }
    @keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  `,
})
export class WaterfallComponent {
  claimed = input.required<number>();
  approved = input.required<number>();
  steps = input.required<WaterfallStep[]>();
  selected = input<string | null>(null);
  select = output<string>();

  cut = computed(() => this.steps().reduce((s, d) => s + d.amount, 0));
  paidPct = computed(() => Math.round((this.approved() / Math.max(this.claimed(), 1)) * 100));
  rows = computed(() => {
    const total = Math.max(this.cut(), 1);
    return this.steps().map((s) => ({ ...s, share: Math.round((s.amount / total) * 100) }));
  });
}
