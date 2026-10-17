import { Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { ChatService } from '../services/chat.service';
import { isLive } from '../services/api.service';

@Component({
  selector: 'app-dispute-review', standalone: true, imports: [MatButtonModule],
  template: `@if (live) {
    <section class="card" id="ai-review">
      <h2>Investigate deductions or rejection</h2>
      <p>Understand the insurer’s decision and prepare a response grounded in your documents.</p>
      <ol class="investigation-path"><li>Check documents and amounts</li><li>Examine each reason and policy clause</li><li>Prepare a checklist and editable letter</li></ol>
      <label for="dispute-clarification">Any clarification? (optional)</label>
      <textarea id="dispute-clarification" rows="2" maxlength="350" [value]="clarification()"
        (input)="clarification.set($any($event.target).value)"></textarea>
      <button mat-flat-button type="button" [disabled]="chat.busy()" (click)="run()">Investigate with Nessi</button>
      <p class="small muted">Your investigation opens in full chat. Missing evidence stays explicit; only the insurer can confirm a claim decision.</p>
    </section>
  }`,
  styles: `.investigation-path { display:flex;flex-wrap:wrap;gap:12px 28px;padding-left:20px;font-size:.88rem;color:var(--cn-muted);margin:20px 0; } textarea { display:block; width:100%; box-sizing:border-box; margin:8px 0 12px; padding:10px; font:inherit; color:var(--cn-ink); background:var(--cn-surface); border:1px solid var(--cn-border); border-radius:8px; }`,
})
export class DisputeReviewComponent {
  readonly chat = inject(ChatService);
  readonly live = isLive('settlement');
  readonly clarification = signal('');
  run(): void {
    this.chat.ask('Investigate my settlement deductions or rejection, check the policy and prepare a clarification letter. ' + this.clarification().trim());
    this.chat.expand();
  }
}
