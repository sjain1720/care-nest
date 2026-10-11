import { Component, inject, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { Citation } from '../models/models';
import { CitationViewerService } from '../services/citation-viewer.service';

@Component({
  selector: 'app-citation-chip',
  standalone: true,
  imports: [MatIconModule],
  template: `
    <button type="button" class="cite-chip" (click)="viewer.open(citation())"
            [attr.aria-label]="'Open source: ' + citation().docName + ', page ' + citation().page + ', ' + citation().clause">
      <mat-icon class="icon-sm">description</mat-icon>
      Page {{ citation().page }} · {{ citation().clause }}
    </button>
  `,
})
export class CitationChipComponent {
  citation = input.required<Citation>();
  viewer = inject(CitationViewerService);
}
