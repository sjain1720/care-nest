import { Component, HostListener, computed, inject } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { CitationViewerService } from '../services/citation-viewer.service';
import { TranslatePipe } from './translate.pipe';

// Only same-origin paths ("/x", not "//host") may be loaded into the iframe.
const SAME_ORIGIN_PATH = /^\/(?!\/)/;

/** Side panel that shows the exact source of a citation (page, clause, quote and, when available, the PDF page). */
@Component({
  selector: 'app-citation-drawer',
  standalone: true,
  imports: [MatButtonModule, MatIconModule, TranslatePipe],
  template: `
    @if (viewer.current(); as c) {
      <div class="backdrop" (click)="viewer.close()"></div>
      <aside class="drawer" role="dialog" aria-modal="true" [attr.aria-label]="('Source' | t) + ': ' + c.docName + ', ' + ('Page' | t) + ' ' + c.page">
        <header class="row">
          <div>
            <div class="muted small">{{ c.docName }}</div>
            <h2>{{ 'Page' | t }} {{ c.page }} · {{ c.clause }}</h2>
          </div>
          <span class="spacer"></span>
          <button mat-icon-button (click)="viewer.close()" [attr.aria-label]="'Close source' | t"><mat-icon>close</mat-icon></button>
        </header>
        <div class="look">{{ 'Look for these words on page' | t }} {{ c.page }}:</div>
        <blockquote>{{ c.quote }}</blockquote>
        @if (pdfSrc(); as src) {
          <iframe [src]="src" [title]="c.docName + ', ' + ('Page' | t) + ' ' + c.page"></iframe>
          <a class="open-full" [href]="fullUrl()" target="_blank" rel="noopener"><mat-icon>open_in_new</mat-icon> {{ 'Open the full document' | t }}</a>
        } @else {
          <p class="muted small">{{ 'The page will appear here once the real document is uploaded.' | t }}</p>
        }
      </aside>
    }
  `,
  styles: `
    .backdrop { position: fixed; inset: 0; background: rgba(15, 23, 42, .35); z-index: 40; }
    .drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(520px, 100vw); background: var(--cn-surface);
              z-index: 41; padding: 16px 20px; box-shadow: -8px 0 24px rgba(0,0,0,.15); display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
    h2 { margin: 0; }
    blockquote { margin: 0; padding: 12px 14px; background: var(--cn-quote-bg); border-left: 4px solid var(--cn-quote-line); border-radius: 6px; font-size: .95rem; }
    iframe { flex: 1; min-height: 60vh; border: 1px solid var(--cn-border); border-radius: 8px; background: #fff; }
    .look { font-size: .8rem; font-weight: 600; color: var(--cn-muted); margin-bottom: -6px; }
    .open-full { display: inline-flex; align-items: center; gap: 6px; min-height: 44px; color: var(--cn-link); font-weight: 600; }
    .open-full mat-icon { font-size: 18px; width: 18px; height: 18px; }
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

  /** Plain href (Angular sanitizes it); only same-origin paths get here because pdfSrc checks first. */
  fullUrl = computed(() => {
    const c = this.viewer.current();
    return c?.docUrl && SAME_ORIGIN_PATH.test(c.docUrl) ? `${c.docUrl}#page=${c.page}` : null;
  });

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.viewer.close();
  }
}
