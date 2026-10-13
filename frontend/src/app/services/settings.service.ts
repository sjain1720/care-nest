import { Injectable, effect, signal } from '@angular/core';

export type Lang = 'en' | 'hi';
export type TextSize = 'sm' | 'md' | 'lg' | 'xl';

const SCALE: Record<TextSize, string> = { sm: '0.9375', md: '1', lg: '1.125', xl: '1.25' };
const KEY_LANG = 'carenest.lang';
const KEY_SIZE = 'carenest.textSize';

function read<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key) as T | null;
    return v && allowed.includes(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* private mode: keep for this visit only */ }
}

/** Display settings: language and text size, saved in this browser. */
@Injectable({ providedIn: 'root' })
export class SettingsService {
  // The language choice is hidden in the UI, so always start in English (a saved Hindi choice can't be switched back).
  readonly lang = signal<Lang>('en');
  readonly textSize = signal<TextSize>(read(KEY_SIZE, ['sm', 'md', 'lg', 'xl'] as const, 'md'));
  readonly sizes: TextSize[] = ['sm', 'md', 'lg', 'xl'];

  constructor() {
    effect(() => {
      document.documentElement.lang = this.lang();
      save(KEY_LANG, this.lang());
    });
    effect(() => {
      // styles.css turns this into the root font size (smaller base on phones).
      document.documentElement.style.setProperty('--cn-text-scale', SCALE[this.textSize()]);
      save(KEY_SIZE, this.textSize());
    });
  }

  smaller(): void {
    const i = this.sizes.indexOf(this.textSize());
    if (i > 0) this.textSize.set(this.sizes[i - 1]);
  }

  bigger(): void {
    const i = this.sizes.indexOf(this.textSize());
    if (i < this.sizes.length - 1) this.textSize.set(this.sizes[i + 1]);
  }
}
