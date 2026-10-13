import { Component, inject, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { Citation } from '../models/models';
import { CitationViewerService } from '../services/citation-viewer.service';
import { TranslatePipe } from './translate.pipe';

@Component({
  selector: 'app-citation-chip',
  standalone: true,
  imports: [MatIconModule, TranslatePipe],
  template: `
    <button type="button" class="cite-chip" (click)="viewer.open(citation())"
            [attr.aria-label]="('Open source' | t) + ': ' + citation().docName + ', ' + ('Page' | t) + ' ' + citation().page + ', ' + citation().clause">
      <mat-icon class="icon-sm">description</mat-icon>
      {{ 'Page' | t }} {{ citation().page }} · {{ citation().clause }}
    </button>
  `,
})
export class CitationChipComponent {
  citation = input.required<Citation>();
  viewer = inject(CitationViewerService);
}
