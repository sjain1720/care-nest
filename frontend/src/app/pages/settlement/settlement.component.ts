import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { InrPipe } from '../../shared/inr.pipe';
import { CitationChipComponent } from '../../shared/citation-chip.component';
import { TrustPillComponent } from '../../shared/trust-pill.component';

// Dark enough for white text (WCAG AA).
const SEGMENT_COLORS = ['#b42318', '#b45309', '#475569', '#0e7490', '#6d28d9'];

@Component({
  selector: 'app-settlement',
  standalone: true,
  imports: [DatePipe, RouterLink, MatButtonModule, MatIconModule, InrPipe, CitationChipComponent, TrustPillComponent],
  templateUrl: './settlement.component.html',
  styles: `
    .totals { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .totals .value { font-size: 1.4rem; }
    .totals .deducted .value { color: var(--cn-bad); }
    @media (max-width: 599px) { .totals { grid-template-columns: 1fr; } }
    .math { margin-top: 12px; }
    .bar { display: flex; height: 44px; border-radius: 10px; overflow: hidden; margin: 12px 0 8px; }
    .seg { border: 0; color: #fff; font: inherit; font-size: .8rem; font-weight: 600; cursor: pointer; padding: 0 6px;
           display: flex; align-items: center; justify-content: center; min-width: 48px; white-space: nowrap; overflow: hidden; }
    .seg.selected { outline: 3px solid var(--cn-ink); outline-offset: -3px; }
    .legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: .85rem; }
    .dot { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; }
    .deduction { border-left: 6px solid; }
    .deduction summary { list-style: none; cursor: pointer; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .deduction summary::-webkit-details-marker { display: none; }
    .deduction .title { font-weight: 600; flex: 1; min-width: 180px; }
    .deduction .amount { font-size: 1.15rem; }
    .section-label { font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; color: var(--cn-muted); margin: 14px 0 4px; }
    .insurer { background: var(--cn-bg); border-radius: 8px; padding: 8px 12px; font-style: italic; }
    ul.plain { margin: 4px 0; padding-left: 20px; }
    .questions li { margin-bottom: 4px; }
  `,
})
export class SettlementComponent {
  private api = inject(ApiService);
  settlement = toSignal(this.api.getSettlement());
  bill = toSignal(this.api.getBill());
  /** undefined = nothing chosen yet, so the first unexplained deduction is opened. */
  private chosen = signal<string | null | undefined>(undefined);
  open = computed(() => {
    const chosen = this.chosen();
    if (chosen !== undefined) return chosen;
    const ds = this.settlement()?.deductions ?? [];
    return (ds.find((d) => d.trust === 'unknown') ?? ds[0])?.id ?? null;
  });

  totalDeducted = computed(() => this.settlement()?.deductions.reduce((s, d) => s + d.amount, 0) ?? 0);
  explained = computed(() => this.settlement()?.deductions.filter((d) => d.trust !== 'unknown').reduce((s, d) => s + d.amount, 0) ?? 0);
  arithmeticOk = computed(() => {
    const s = this.settlement();
    return !!s && s.claimedAmount - this.totalDeducted() === s.approvedAmount;
  });

  color(index: number): string {
    return SEGMENT_COLORS[index % SEGMENT_COLORS.length];
  }

  share(amount: number): number {
    return this.totalDeducted() ? (amount / this.totalDeducted()) * 100 : 0;
  }

  select(id: string): void {
    this.chosen.set(id);
    setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }

  onToggle(id: string, event: Event): void {
    const isOpen = (event.target as HTMLDetailsElement).open;
    if (isOpen) this.chosen.set(id);
    else if (this.open() === id) this.chosen.set(null);
  }
}
