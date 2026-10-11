import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { BillCheck, BillTag } from '../../models/models';
import { InrPipe } from '../../shared/inr.pipe';
import { CitationViewerService } from '../../services/citation-viewer.service';

const TAGS: Record<BillTag, { label: string; tone: string }> = {
  likely_payable: { label: 'Likely payable', tone: 'ok' },
  possibly_non_payable: { label: 'Possibly not payable', tone: 'bad' },
  needs_clarification: { label: 'Needs clarification', tone: 'warn' },
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
  imports: [RouterLink, MatButtonModule, MatIconModule, InrPipe],
  templateUrl: './bill-check.component.html',
  styles: `
    .totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
    .check { display: flex; gap: 10px; align-items: flex-start; padding: 10px 0; border-top: 1px solid var(--cn-border); }
    .check:first-of-type { border-top: 0; }
    .check mat-icon { flex: none; }
    .tone-text-bad { color: var(--cn-bad); } .tone-text-warn { color: var(--cn-warn); } .tone-text-info { color: var(--cn-primary); }
    .estimate { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; margin: 8px 0 12px; }
    .estimate div { background: var(--cn-bg); border-radius: 10px; padding: 10px; }
    .estimate .likely { background: var(--cn-warn-soft); }
    .estimate .value { font-size: 1.2rem; font-weight: 700; }
    @media (max-width: 599px) { .estimate { grid-template-columns: 1fr; } }
    .table-wrap { overflow-x: auto; }
    ul.plain { margin: 4px 0; padding-left: 20px; }
  `,
})
export class BillCheckComponent {
  private api = inject(ApiService);
  private viewer = inject(CitationViewerService);
  bill = toSignal(this.api.getBill());

  issues = computed(() => (this.bill()?.checks ?? []).filter((c) => c.severity !== 'info'));
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
