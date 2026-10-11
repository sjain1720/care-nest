import { Injectable, signal } from '@angular/core';
import { Citation } from '../models/models';

// Synthetic PDFs from demo-data/make_demo_pdfs.py, used when a citation has no docUrl (demo data).
const DEMO_DOC_URLS: Record<string, string> = {
  policy: '/demo/sample_policy.pdf',
  settlement: '/demo/settlement_letter.pdf',
  bill: '/demo/hospital_bill.pdf',
};

/** Opens the source-document drawer for a clicked citation chip. */
@Injectable({ providedIn: 'root' })
export class CitationViewerService {
  readonly current = signal<Citation | null>(null);

  open(citation: Citation): void {
    this.current.set({ ...citation, docUrl: citation.docUrl ?? DEMO_DOC_URLS[citation.docId] });
  }

  close(): void {
    this.current.set(null);
  }
}
