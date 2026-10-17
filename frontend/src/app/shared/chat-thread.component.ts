import { Component, ElementRef, effect, inject, input, output } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { ChatService, followUps } from '../services/chat.service';
import { isLive } from '../services/api.service';
import { SettingsService } from '../services/settings.service';
import { AgentProgressComponent } from './agent-progress.component';
import { AnswerCardComponent } from './answer-card.component';
import { TranslatePipe } from './translate.pipe';

/** The conversation itself; used by the floating chat and the Ask page. */
@Component({
  selector: 'app-chat-thread',
  standalone: true,
  imports: [MatIconModule, AgentProgressComponent, AnswerCardComponent, TranslatePipe],
  template: `
    @if (settings.lang() === 'hi' && !liveAsk) {
      <p class="lang-note" lang="hi">डेमो में जवाब अंग्रेज़ी में हैं। अपने काग़ज़ों (लाइव मोड) के साथ जवाब हिन्दी में मिलेंगे।</p>
    }
    <div class="thread" aria-live="polite">
      @for (m of chat.messages(); track m.id; let i = $index; let last = $last) {
        @if (m.role === 'user') {
          <div class="bubble-user">{{ m.text }}</div>
        } @else {
          <div class="bubble-ai" [class.compact]="compact()">
            @if (m.steps?.length) {
              @if (m.answer || m.text) { <details class="completed-steps"><summary>View {{ m.steps?.length }} processing steps</summary><app-agent-progress [steps]="m.steps ?? []" [running]="false" /></details> }
              @else { <app-agent-progress [steps]="m.steps ?? []" [running]="true" /> }
            } @else if (!m.answer && !m.text) {
              <div class="typing" aria-label="Thinking"><span></span><span></span><span></span></div>
            }
            @if (m.answer; as a) {
              <hr>
              <app-answer-card [answer]="a" (actionSelected)="chat.closePanel()" />
            }
            @if (m.text) { <p class="error">{{ m.text }}</p> }
          </div>
          @if (last && m.answer && !chat.busy()) {
            <div class="follow" role="group" [attr.aria-label]="'You might also ask' | t">
              <span class="follow-label">{{ 'You might also ask' | t }}</span>
              @for (q of nextQuestions(m.answer.nextAction?.route, i); track q) {
                <button type="button" class="chip" (click)="pick.emit(q)"><mat-icon>subdirectory_arrow_right</mat-icon>{{ q }}</button>
              }
            </div>
          }
        }
      } @empty {
        <div class="empty">
          <div class="spark"><mat-icon>auto_awesome</mat-icon></div>
          <h2>{{ 'What would you like to know?' | t }}</h2>
          @if (compact()) { <p class="muted small">{{ chat.contextLabel() }}</p> }
          <div class="prompts">
            @for (p of prompts(); track p) {
              <button type="button" class="prompt" (click)="pick.emit(p)">{{ p }}</button>
            }
          </div>
        </div>
      }
    </div>
  `,
  styles: `
    .thread { display: flex; flex-direction: column; gap: 12px; }
    .bubble-user { align-self: flex-end; max-width: 85%; background: var(--cn-bubble); color: #fff; padding: 10px 14px;
                   border-radius: 16px 16px 4px 16px; }
    .bubble-ai { background: var(--cn-surface); border: 1px solid var(--cn-border); border-radius: 16px 16px 16px 4px; padding: 14px;
                 box-shadow: var(--cn-shadow); }
    .bubble-ai.compact { padding: 12px; }
    hr { border: 0; border-top: 1px solid var(--cn-border); margin: 12px 0; }
    .error { margin: 0; color: var(--cn-bad); }
    .empty { text-align: center; padding: 16px 4px; }
    .spark { width: 56px; height: 56px; margin: 0 auto 8px; border-radius: 50%; display: grid; place-items: center;
             background: linear-gradient(135deg, var(--cn-navy), var(--cn-navy-700)); color: var(--cn-green-bright); }
    .prompts { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
    .prompt { text-align: left; padding: 10px 14px; border: 1px solid var(--cn-border); border-radius: 12px; background: var(--cn-surface);
              color: var(--cn-link); font: inherit; font-size: .9rem; cursor: pointer; transition: border-color .15s, background .15s, transform .15s; }
    .prompt:hover { border-color: var(--cn-green); background: var(--cn-green-soft); transform: translateX(2px); }
    .typing { display: inline-flex; gap: 4px; padding: 4px 0; }
    .typing span { width: 8px; height: 8px; border-radius: 50%; background: var(--cn-border-strong); }
    @media (prefers-reduced-motion: no-preference) {
      .bubble-user, .bubble-ai { animation: cn-rise .3s var(--cn-ease) backwards; }
      .typing span { animation: bounce 1s infinite ease-in-out; }
      .typing span:nth-child(2) { animation-delay: .15s; }
      .typing span:nth-child(3) { animation-delay: .3s; }
    }
    @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); opacity: .5; } 40% { transform: translateY(-5px); opacity: 1; } }
    .follow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: -4px; }
    .follow-label { width: 100%; font-size: .75rem; font-weight: 600; color: var(--cn-muted); }
    .chip { display: inline-flex; align-items: center; gap: 4px; min-height: 36px; padding: 4px 12px 4px 8px; border-radius: 999px; cursor: pointer;
            border: 1px solid var(--cn-border-strong); background: var(--cn-surface); color: var(--cn-link); font: inherit; font-size: .82rem; text-align: left; }
    .chip mat-icon { font-size: 16px; width: 16px; height: 16px; color: var(--cn-green-strong); flex: none; }
    @media (hover: hover) { .chip:hover { border-color: var(--cn-green); background: var(--cn-green-soft); } }
    .lang-note { margin: 0 0 10px; padding: 8px 12px; border-radius: 10px; background: var(--cn-warn-soft); color: var(--cn-warn); font-size: .85rem; }
  `,
})
export class ChatThreadComponent {
  readonly chat = inject(ChatService);
  readonly settings = inject(SettingsService);
  readonly liveAsk = isLive('ask');
  private host = inject<ElementRef<HTMLElement>>(ElementRef);

  prompts = input<string[]>([]);
  compact = input(false);
  pick = output<string>();

  nextQuestions(route: string | undefined, answerIndex: number): string[] {
    const asked = this.chat.messages().at(answerIndex - 1)?.text ?? '';
    return followUps(route, asked);
  }

  constructor() {
    // Keep the newest message in view as steps and answers arrive.
    effect(() => {
      if (!this.chat.messages().length) return;
      setTimeout(() => this.host.nativeElement.querySelector('.thread')?.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'end' }));
    });
  }
}
