import { Component, OnDestroy, OnInit, computed, inject, input } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ChatService } from '../../services/chat.service';
import { ApiService } from '../../services/api.service';
import { ChatThreadComponent } from '../../shared/chat-thread.component';
import { ChatBarComponent } from '../../shared/chat-bar.component';

@Component({
  selector: 'app-ask', standalone: true,
  imports: [MatButtonModule, MatIconModule, RouterLink, ChatThreadComponent, ChatBarComponent],
  templateUrl: './ask.component.html', styleUrl: './ask.component.css',
})
export class AskComponent implements OnInit, OnDestroy {
  readonly chat = inject(ChatService);
  private api = inject(ApiService);
  readonly policy = toSignal(this.api.getPolicy());
  readonly claim = toSignal(this.api.getCase());
  readonly prompts = computed(() => this.chat.workspace.mode() !== 'general' && (this.policy() || this.claim()?.documents.length)
    ? ['What is my room-rent limit?', 'Why was money deducted from my claim?', 'Which documents am I missing?', 'What should I ask the insurer?']
    : ['What is a waiting period?', 'How do I question a deduction?', 'What documents help prepare a claim?']);
  q = input<string>();
  ngOnInit(): void {
    this.chat.pageVisible.set(true);
    this.chat.closePanel();
    this.chat.markRead();
    if (this.q()) this.chat.send(this.q()!);
  }
  ngOnDestroy(): void { this.chat.pageVisible.set(false); }
  send(text: string): void { this.chat.send(text); }
}
