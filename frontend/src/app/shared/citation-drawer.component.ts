import { Component, HostListener, computed, inject } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { CitationViewerService } from '../services/citation-viewer.service';

// Only same-origin paths ("/x", not "//host") may be loaded into the iframe.
const SAME_ORIGIN_PATH = /^\/(?!\/)/;

/** Side panel that shows the exact source of a citation (page, clause, quote and, when available, the PDF page). */
@Component({
  selector: 'app-citation-drawer',
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  template: `
    @if (viewer.current(); as c) {
      <div class="backdrop" (click)="viewer.close()"></div>
      <aside class="drawer" role="dialog" aria-modal="true" [attr.aria-label]="'Source: ' + c.docName + ', page ' + c.page">
        <header class="row">
          <div>
            <div class="muted small">{{ c.docName }}</div>
            <h2>Page {{ c.page }} · {{ c.clause }}</h2>
          </div>
          <span class="spacer"></span>
          <button mat-icon-button (click)="viewer.close()" aria-label="Close source"><mat-icon>close</mat-icon></button>
        </header>
        <blockquote>{{ c.quote }}</blockquote>
        @if (pdfSrc(); as src) {
          <iframe [src]="src" title="Source document page"></iframe>
        } @else {
          <p class="muted small">The highlighted page will appear here once the real document is connected.</p>
        }
      </aside>
    }
  `,
  styles: `
    .backdrop { position: fixed; inset: 0; background: rgba(15, 23, 42, .35); z-index: 40; }
    .drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(520px, 100vw); background: var(--cn-surface);
              z-index: 41; padding: 16px 20px; box-shadow: -8px 0 24px rgba(0,0,0,.15); display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
    h2 { margin: 0; }
    blockquote { margin: 0; padding: 12px 14px; background: #fff8c5; border-left: 4px solid #d4a72c; border-radius: 6px; font-size: .95rem; }
    iframe { flex: 1; min-height: 60vh; border: 1px solid var(--cn-border); border-radius: 8px; }
  `,
})
export class CitationDrawerComponent {
  viewer = inject(CitationViewerService);
  private sanitizer = inject(DomSanitizer);

  pdfSrc = computed<SafeResourceUrl | null>(() => {
    const c = this.viewer.current();
    if (!c?.docUrl || !SAME_ORIGIN_PATH.test(c.docUrl)) return null;
    return this.sanitizer.bypassSecurityTrustResourceUrl(`${c.docUrl}#page=${c.page}`);
  });

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.viewer.close();
  }
}
