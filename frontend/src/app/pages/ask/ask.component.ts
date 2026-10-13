import { Component, OnDestroy, OnInit, inject, input } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { ChatService, chatContext } from '../../services/chat.service';
import { ChatThreadComponent } from '../../shared/chat-thread.component';

@Component({
  selector: 'app-ask',
  standalone: true,
  imports: [MatButtonModule, MatIconModule, ChatThreadComponent, TranslatePipe],
  templateUrl: './ask.component.html',
  styles: `
    .page { display: flex; flex-direction: column; min-height: calc(100vh - 220px); max-width: 820px; }
    app-chat-thread { flex: 1; }
  `,
})
export class AskComponent implements OnInit, OnDestroy {
  readonly chat = inject(ChatService);

  /** Pre-filled question from ?q= (e.g. from the dashboard). */
  q = input<string>();

  readonly prompts = chatContext('/').prompts;

  ngOnInit(): void {
    this.chat.pageVisible.set(true);
    this.chat.closePanel();
    this.chat.unread.set(0);
    const q = this.q();
    if (q) this.chat.send(q);
  }

  ngOnDestroy(): void {
    this.chat.pageVisible.set(false);
  }

  send(text: string): void {
    this.chat.send(text);
  }
}
