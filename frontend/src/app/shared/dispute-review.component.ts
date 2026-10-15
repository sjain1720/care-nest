import { Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { ChatService } from '../services/chat.service';
import { isLive } from '../services/api.service';

@Component({
  selector: 'app-dispute-review', standalone: true, imports: [MatButtonModule],
  template: `@if (live) {
    <section class="card" id="ai-review">
      <h2>Investigate deductions or rejection</h2>
      <p>Compare policy, reviewed bill and insurer decision; get sourced findings, a clarification checklist and an editable letter.</p>
      <label for="dispute-clarification">Any clarification? (optional)</label>
      <textarea id="dispute-clarification" rows="2" maxlength="350" [value]="clarification()"
        (input)="clarification.set($any($event.target).value)"></textarea>
      <button mat-flat-button type="button" [disabled]="chat.busy()" (click)="run()">Investigate my decision</button>
      <p class="small muted">The investigation uses the same guest conversation. Related wording does not prove that a deduction is justified.</p>
    </section>
  }`,
  styles: `textarea { display:block; width:100%; box-sizing:border-box; margin:8px 0 12px; padding:10px; font:inherit; color:var(--cn-ink); background:var(--cn-surface); border:1px solid var(--cn-border); border-radius:8px; }`,
})
export class DisputeReviewComponent {
  readonly chat = inject(ChatService);
  readonly live = isLive('settlement');
  readonly clarification = signal('');
  run(): void {
    this.chat.ask('Investigate my settlement deductions or rejection, check the policy and prepare a clarification letter. ' + this.clarification().trim());
  }
}
