import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { ChatService } from '../../services/chat.service';
import { ChatBarComponent } from '../../shared/chat-bar.component';

@Component({
  selector: 'app-home', standalone: true,
  imports: [RouterLink, MatIconModule, ChatBarComponent],
  templateUrl: './home.component.html', styleUrl: './home.component.css',
})
export class HomeComponent {
  readonly chat = inject(ChatService);
  readonly prompts = () => ['What is a waiting period?', 'How do I question a deduction?', 'What documents help prepare a claim?'];
}
