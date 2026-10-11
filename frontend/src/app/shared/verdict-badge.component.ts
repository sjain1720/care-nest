import { Component, computed, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { Verdict } from '../models/models';

const VERDICTS: Record<Verdict, { label: string; icon: string; tone: string }> = {
  covered: { label: 'Covered', icon: 'check_circle', tone: 'ok' },
  partial: { label: 'Covered with limits', icon: 'rule', tone: 'warn' },
  not_covered: { label: 'Not covered yet', icon: 'block', tone: 'bad' },
  needs_checking: { label: 'Needs checking', icon: 'error_outline', tone: 'warn' },
  cant_confirm: { label: "Can't confirm", icon: 'help_outline', tone: 'unknown' },
  info: { label: 'Guidance', icon: 'info', tone: 'info' },
};

@Component({
  selector: 'app-verdict-badge',
  standalone: true,
  imports: [MatIconModule],
  template: `<span [class]="'pill tone-' + meta().tone"><mat-icon class="icon-sm">{{ meta().icon }}</mat-icon>{{ meta().label }}</span>`,
})
export class VerdictBadgeComponent {
  verdict = input.required<Verdict>();
  meta = computed(() => VERDICTS[this.verdict()]);
}
