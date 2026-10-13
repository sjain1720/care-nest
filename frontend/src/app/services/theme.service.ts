import { Injectable, signal } from '@angular/core';

export type Theme = 'dark' | 'light';
// v2: the light design became the default, so earlier saved choices start fresh.
const KEY = 'carenest.theme.v2';

/** Light by default. index.html applies the saved choice before the app starts; this service switches it. */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<Theme>(document.documentElement.dataset['theme'] === 'dark' ? 'dark' : 'light');

  /** Switches theme with a circle growing from the toggle button (instant when reduced motion is on). */
  toggle(origin?: HTMLElement): void {
    const next: Theme = this.theme() === 'dark' ? 'light' : 'dark';
    const apply = () => {
      document.documentElement.dataset['theme'] = next;
      try { localStorage.setItem(KEY, next); } catch { /* private mode: keep for this visit only */ }
      this.theme.set(next);
    };

    const root = document.documentElement;
    if (!origin || !document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      apply();
      return;
    }
    const r = origin.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

    root.classList.add('cn-theme-switch');
    const transition = document.startViewTransition(apply);
    transition.ready
      .then(() => root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 550, easing: 'cubic-bezier(.2, .7, .2, 1)', pseudoElement: '::view-transition-new(root)' },
      ))
      .catch(() => undefined);
    transition.finished.catch(() => undefined).finally(() => root.classList.remove('cn-theme-switch'));
  }
}
