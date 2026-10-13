import { Component, computed, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { Trust } from '../models/models';
import { TranslatePipe } from './translate.pipe';

const TRUST: Record<Trust, { label: string; icon: string; tone: string }> = {
  supported: { label: 'Matches your papers', icon: 'verified', tone: 'ok' },
  check: { label: 'Please check', icon: 'error_outline', tone: 'warn' },
  unknown: { label: 'No clear reason', icon: 'help_outline', tone: 'unknown' },
};

@Component({
  selector: 'app-trust-pill',
  standalone: true,
  imports: [MatIconModule, TranslatePipe],
  template: `<span [class]="'pill tone-' + meta().tone"><mat-icon class="icon-sm">{{ meta().icon }}</mat-icon>{{ meta().label | t }}</span>`,
})
export class TrustPillComponent {
  trust = input.required<Trust>();
  meta = computed(() => TRUST[this.trust()]);
}
