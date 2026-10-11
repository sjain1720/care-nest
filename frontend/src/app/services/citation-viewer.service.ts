import { Injectable, signal } from '@angular/core';
import { Citation } from '../models/models';

/** Opens the source-document drawer for a clicked citation chip. */
@Injectable({ providedIn: 'root' })
export class CitationViewerService {
  readonly current = signal<Citation | null>(null);

  open(citation: Citation): void {
    this.current.set(citation);
  }

  close(): void {
    this.current.set(null);
  }
}
