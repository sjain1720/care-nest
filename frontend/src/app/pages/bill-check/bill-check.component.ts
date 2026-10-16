import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { DocumentPreviewComponent } from '../../shared/document-preview.component';
import { ApiService } from '../../services/api.service';
import { BillCheck, BillTag } from '../../models/models';
import { InrPipe, formatInr } from '../../shared/inr.pipe';
import { NextStep, NextStepsComponent } from '../../shared/next-steps.component';
import { EmptyStateComponent, SkeletonComponent } from '../../shared/page-states.component';
import { GlossComponent } from '../../shared/gloss.component';
import { CitationViewerService } from '../../services/citation-viewer.service';
import { CitationChipComponent } from '../../shared/citation-chip.component';
import { BillReviewComponent } from './bill-review.component';

const TAGS: Record<BillTag, { label: string; tone: string }> = {
  likely_payable: { label: 'No heuristic flag', tone: 'ok' },
  possibly_non_payable: { label: 'May not be paid', tone: 'bad' },
  needs_clarification: { label: 'Not clear yet', tone: 'warn' },
};

const SEVERITY: Record<BillCheck['severity'], { icon: string; tone: string }> = {
  high: { icon: 'report', tone: 'bad' },
  medium: { icon: 'error_outline', tone: 'warn' },
  info: { icon: 'info', tone: 'info' },
};

/** Hospital bill check: missing pages, arithmetic, room limit, items insurers usually don't pay, and an estimate. */
@Component({
  selector: 'app-bill-check',
  standalone: true,
  imports: [DocumentPreviewComponent, RouterLink, MatButtonModule, MatIconModule, InrPipe, NextStepsComponent, SkeletonComponent, EmptyStateComponent, GlossComponent, BillReviewComponent, TranslatePipe, CitationChipComponent],
  templateUrl: './bill-check.component.html',
  styles: `
    .totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
    .check { display: flex; gap: 10px; align-items: flex-start; padding: 10px 0; border-top: 1px solid var(--cn-border); }
    .check:first-of-type { border-top: 0; }
    .check mat-icon { flex: none; }
    .tone-text-bad { color: var(--cn-bad); } .tone-text-warn { color: var(--cn-warn); } .tone-text-info { color: var(--cn-primary); }
    .estimate { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; margin: 8px 0 12px; }
    .estimate > div { background: var(--cn-bg); border-radius: 10px; padding: 10px; }
    .estimate .likely { background: var(--cn-warn-soft); }
    .estimate .value { font-size: 1.2rem; font-weight: 700; }
    @media (max-width: 599px) { .estimate { grid-template-columns: 1fr; } }
    .table-wrap { overflow-x: auto; }
    ul.plain { margin: 4px 0; padding-left: 20px; }
  `,
})
export class BillCheckComponent {
  evidenceLoading = signal(false);
  evidenceError = signal<string | null>(null);
  comparePolicy(): void {
    this.evidenceLoading.set(true); this.evidenceError.set(null);
    this.api.compareBillPolicy().subscribe({
      next: () => this.evidenceLoading.set(false),
      error: (e) => { this.evidenceLoading.set(false); this.evidenceError.set(e?.error?.detail || 'Comparison failed. Please retry.'); },
    });
  }

  private api = inject(ApiService);
  private viewer = inject(CitationViewerService);
  bill = toSignal(this.api.getBill());
  claimCase = toSignal(this.api.getCase());
  settlement = toSignal(this.api.getSettlement());

  issues = computed(() => (this.bill()?.checks ?? []).filter((c) => c.severity !== 'info'));

  nextSteps = computed<NextStep[]>(() => {
    const b = this.bill();
    if (!b) return [];
    const steps: NextStep[] = [];
    if (b.reviewed === false) steps.push({ text: 'Check the details we read against your paper bill.', action: 'Check now', route: '/case/bill', fragment: 'review' });
    const high = this.issues().find((c) => c.severity === 'high') ?? this.issues()[0];
    if (high) steps.push({ text: `Ask the hospital billing desk about this: ${high.message}`, action: 'See details', route: '/case/bill', fragment: 'checks' });
    if (b.estimate) steps.push({ text: `Keep about ${formatInr(b.estimate.likely)} ready. The insurer may not pay this part.`, action: 'See why', route: '/case/bill', fragment: 'estimate' });
    if (this.settlement()) {
      steps.push({ text: 'Compare this with what the insurer actually cut.', action: 'See the cuts', route: '/case/settlement' });
    } else {
      steps.push({ text: "When the insurer's letter arrives, add it. We will explain each cut.", action: "Add the insurer's letter", route: '/upload' });
    }
    steps.push({ text: 'Keep the original bill and all payment receipts. You need them for the claim.', action: 'Papers list', route: '/case', fragment: 'checklist' });
    return steps;
  });
  sums = computed(() => {
    const items = this.bill()?.items ?? [];
    const by = (tag: BillTag) => items.filter((i) => i.tag === tag).reduce((s, i) => s + i.amount, 0);
    return { payable: by('likely_payable'), notPayable: by('possibly_non_payable'), unclear: by('needs_clarification') };
  });

  tag(t: BillTag) {
    return TAGS[t];
  }

  severity(s: BillCheck['severity']) {
    return SEVERITY[s];
  }

  openPage(page: number): void {
    const b = this.bill();
    if (!b) return;
    this.viewer.open({ docId: 'bill', docName: 'Hospital bill', page, clause: 'Bill', quote: `${b.hospital} – page ${page}`, docUrl: b.docUrl });
  }
}
