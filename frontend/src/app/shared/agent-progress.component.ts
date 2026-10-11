import { Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { AgentStep } from '../models/models';

/** Live list of what the agents are doing, e.g. "Reading page 9 · Clause 4.2". */
@Component({
  selector: 'app-agent-progress',
  standalone: true,
  imports: [MatIconModule],
  template: `
    <ol class="steps" aria-live="polite">
      @for (step of steps(); track $index; let last = $last) {
        <li [class.active]="last && running()">
          @if (last && running()) {
            <span class="spinner" aria-hidden="true"></span>
          } @else {
            <mat-icon class="icon-sm done">check</mat-icon>
          }
          <span class="label">{{ step.label }}</span>
          <span class="agent">{{ step.agent }}</span>
        </li>
      }
    </ol>
  `,
  styles: `
    .steps { list-style: none; margin: 0; padding: 0; font-size: .875rem; }
    li { display: flex; align-items: center; gap: 8px; padding: 3px 0; color: var(--cn-muted); }
    li.active { color: var(--cn-ink); font-weight: 600; }
    .done { color: var(--cn-ok); }
    .agent { margin-left: auto; font-size: .75rem; background: var(--cn-primary-soft); color: var(--cn-primary); padding: 1px 8px; border-radius: 999px; white-space: nowrap; }
    .spinner { width: 14px; height: 14px; border: 2px solid var(--cn-border); border-top-color: var(--cn-primary); border-radius: 50%; animation: spin .8s linear infinite; flex: none; margin: 0 2px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (prefers-reduced-motion: reduce) { .spinner { animation-duration: 2s; } }
  `,
})
export class AgentProgressComponent {
  steps = input.required<AgentStep[]>();
  running = input(false);
}
