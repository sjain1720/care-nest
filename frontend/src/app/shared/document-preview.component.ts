import { Component, computed, inject, input, signal } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { MatIconModule } from '@angular/material/icon';

/** Only our known same-origin document endpoints/assets can be embedded. */
@Component({ selector: 'app-document-preview', standalone: true, imports: [MatIconModule],
 template: `@if (safeUrl(); as src) {
   <section class="document-preview">
     <header><span><mat-icon>description</mat-icon> {{ title() }}</span><a [href]="url()" target="_blank" rel="noopener">Open original <mat-icon>open_in_new</mat-icon></a></header>
     <button class="preview-toggle" type="button" (click)="expanded.set(!expanded())" [attr.aria-expanded]="expanded()">{{ expanded() ? 'Hide document preview' : 'Show document preview' }}</button>
     @if (expanded()) { <iframe [src]="src" [title]="title()" loading="lazy"></iframe><p class="small muted">If your browser cannot display this file, use Open original.</p> }
   </section>
 }`,
 styles: `:host{display:block;min-width:0}.document-preview{border:1px solid var(--cn-border);border-radius:14px;overflow:hidden;background:var(--cn-surface)}header{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:16px;background:var(--cn-green-soft);font-size:.82rem}header span,header a{display:flex;align-items:center;gap:6px}a{color:var(--cn-link)}iframe{width:100%;height:560px;border:0;background:white}.preview-toggle{display:block;width:100%;padding:12px;border:0;background:var(--cn-surface);color:var(--cn-link);font:inherit;cursor:pointer}.small{padding:0 12px}@media(max-width:899px){iframe{height:420px}}`,
})
export class DocumentPreviewComponent {
 readonly url = input<string | null | undefined>();
 readonly title = input('Source document');
 readonly expanded = signal(innerWidth >= 1100);
 private sanitizer = inject(DomSanitizer);
 readonly safeUrl = computed(() => {
   const url = this.url();
   return url && /^\/(?:api\/(?:policy\/document|case\/document\/[^/?#]+)|demo\/[\w.-]+\.pdf)(?:[?#].*)?$/.test(url)
     ? this.sanitizer.bypassSecurityTrustResourceUrl(url) : null;
 });
}
