import { DestroyRef, Directive, ElementRef, effect, inject, input } from '@angular/core';
import { formatInr } from './inr.pipe';

const DURATION_MS = 900;

/** Counts a number up from 0 when it first appears or changes, e.g. <strong [cnCountUp]="246000"></strong>. */
@Directive({ selector: '[cnCountUp]', standalone: true })
export class CountUpDirective {
  readonly value = input.required<number>({ alias: 'cnCountUp' });
  readonly format = input<(n: number) => string>(formatInr);
  private el = inject<ElementRef<HTMLElement>>(ElementRef);
  private frame = 0;

  constructor() {
    inject(DestroyRef).onDestroy(() => cancelAnimationFrame(this.frame));
    effect(() => {
      const target = this.value();
      const format = this.format();
      cancelAnimationFrame(this.frame);
      if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
        this.el.nativeElement.textContent = format(target);
        return;
      }
      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / DURATION_MS);
        const eased = 1 - Math.pow(1 - t, 3);
        this.el.nativeElement.textContent = format(Math.round(target * eased));
        if (t < 1) this.frame = requestAnimationFrame(step);
      };
      this.frame = requestAnimationFrame(step);
    });
  }
}
