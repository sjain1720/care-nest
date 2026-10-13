import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { TranslatePipe } from './translate.pipe';

/** Grey placeholder blocks while a page loads (shimmer is off for reduced motion). */
@Component({
  selector: 'app-skeleton',
  standalone: true,
  imports: [TranslatePipe],
  template: `
    <div class="sk" role="status" aria-live="polite" [attr.aria-label]="label() | t">
      <div class="line title"></div>
      <div class="line w60"></div>
      @for (c of cards(); track $index) {
        <div class="block">
          <div class="line w40"></div>
          <div class="line"></div>
          <div class="line w80"></div>
        </div>
      }
      <span class="sr-only">{{ label() | t }}</span>
    </div>
  `,
  styles: `
    .sk { display: flex; flex-direction: column; gap: 12px; }
    .block { display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: var(--cn-radius); border: 1px solid var(--cn-border); background: var(--cn-surface); }
    .line { height: 14px; border-radius: 7px; background: var(--cn-track); }
    .title { height: 26px; width: 55%; }
    .w40 { width: 40%; } .w60 { width: 60%; } .w80 { width: 80%; }
    @media (prefers-reduced-motion: no-preference) {
      .line { background: linear-gradient(90deg, var(--cn-track) 25%, var(--cn-border) 50%, var(--cn-track) 75%); background-size: 200% 100%;
              animation: shimmer 1.4s ease-in-out infinite; }
    }
    @keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
  `,
})
export class SkeletonComponent {
  label = input('Loading…');
  count = input(2);
  cards = () => Array.from({ length: this.count() });
}

/** Friendly "nothing here yet" card with a picture, one sentence and one clear action. */
@Component({
  selector: 'app-empty-state',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule, TranslatePipe],
  // `title` is an input here; drop the native attribute so no English tooltip shows on hover.
  host: { '[attr.title]': 'null' },
  template: `
    <section class="card empty">
      <!-- Simple line drawing: a sheet of paper with a badge showing what is missing. -->
      <div class="art" aria-hidden="true">
        <svg viewBox="0 0 160 120" class="draw">
          <ellipse cx="80" cy="110" rx="58" ry="6" class="shadow" />
          <path d="M28 96c8-16 22-18 30-6" class="leaf" />
          <path d="M132 92c-6-14-18-16-26-6" class="leaf" />
          <path d="M54 14h38l20 20v66a4 4 0 0 1-4 4H54a4 4 0 0 1-4-4V18a4 4 0 0 1 4-4z" class="paper" />
          <path d="M92 14v16a4 4 0 0 0 4 4h16" class="fold" />
          <path d="M62 48h36M62 58h40M62 68h26M62 78h32" class="lines" />
          <path d="M26 30l6 6m0-6l-6 6M128 18l5 5m0-5l-5 5" class="spark" />
          <circle cx="136" cy="52" r="3" class="dot" /><circle cx="22" cy="62" r="2.5" class="dot" />
        </svg>
        <span class="badge"><mat-icon>{{ icon() }}</mat-icon></span>
      </div>
      <h1>{{ title() | t }}</h1>
      <p>{{ text() | t }}</p>
      @if (action() && route()) {
        <a mat-flat-button [routerLink]="route()"><mat-icon>{{ actionIcon() }}</mat-icon> {{ action()! | t }}</a>
      }
      <ng-content />
    </section>
  `,
  styles: `
    .empty { text-align: center; padding: 28px 20px; }
    .empty p { max-width: 520px; margin: 8px auto 16px; color: var(--cn-muted); }
    .art { position: relative; width: 160px; height: 120px; margin: 0 auto 10px; }
    .draw { width: 100%; height: 100%; overflow: visible; }
    .shadow { fill: var(--cn-track); }
    .paper { fill: var(--cn-surface); stroke: var(--cn-border-strong); stroke-width: 2; }
    .fold { fill: none; stroke: var(--cn-border-strong); stroke-width: 2; }
    .lines { fill: none; stroke: var(--cn-track); stroke-width: 4; stroke-linecap: round; }
    .leaf { fill: none; stroke: var(--cn-green); stroke-width: 2.5; stroke-linecap: round; opacity: .7; }
    .spark { fill: none; stroke: var(--cn-green-bright); stroke-width: 2; stroke-linecap: round; }
    .dot { fill: var(--cn-link); opacity: .6; }
    .badge { position: absolute; right: 26px; bottom: 6px; width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center;
             background: var(--cn-green-soft); border: 2px solid var(--cn-surface); box-shadow: var(--cn-shadow); }
    .badge mat-icon { font-size: 26px; width: 26px; height: 26px; color: var(--cn-green-strong); }
    @media (prefers-reduced-motion: no-preference) {
      .lines { stroke-dasharray: 44; stroke-dashoffset: 44; animation: draw .9s ease .2s forwards; }
      .badge { animation: pop .4s var(--cn-ease) .5s backwards; }
      .spark { animation: twinkle 2.4s ease-in-out infinite; }
    }
    @keyframes draw { to { stroke-dashoffset: 0; } }
    @keyframes pop { from { transform: scale(.4); opacity: 0; } to { transform: none; opacity: 1; } }
    @keyframes twinkle { 50% { opacity: .3; } }
  `,
})
export class EmptyStateComponent {
  icon = input('description');
  title = input.required<string>();
  text = input.required<string>();
  action = input<string>();
  actionIcon = input('upload_file');
  route = input<string>('/upload');
}
