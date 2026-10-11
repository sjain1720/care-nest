import { Component, computed, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { Trust } from '../models/models';

const TRUST: Record<Trust, { label: string; icon: string; tone: string }> = {
  supported: { label: 'Supported by your documents', icon: 'verified', tone: 'ok' },
  check: { label: 'Needs checking', icon: 'error_outline', tone: 'warn' },
  unknown: { label: "Can't confirm", icon: 'help_outline', tone: 'unknown' },
};

@Component({
  selector: 'app-trust-pill',
  standalone: true,
  imports: [MatIconModule],
  template: `<span [class]="'pill tone-' + meta().tone"><mat-icon class="icon-sm">{{ meta().icon }}</mat-icon>{{ meta().label }}</span>`,
})
export class TrustPillComponent {
  trust = input.required<Trust>();
  meta = computed(() => TRUST[this.trust()]);
}
