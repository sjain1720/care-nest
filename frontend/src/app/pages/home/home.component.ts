import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { catchError, of } from 'rxjs';
import { ApiService, isFullyLive } from '../../services/api.service';
import { ChatService } from '../../services/chat.service';
import { ChatBarComponent } from '../../shared/chat-bar.component';

@Component({
  selector: 'app-home', standalone: true,
  imports: [RouterLink, MatIconModule, MatProgressBarModule, ChatBarComponent],
  templateUrl: './home.component.html', styleUrl: './home.component.css',
})
export class HomeComponent {
  private api = inject(ApiService);
  private router = inject(Router);
  readonly chat = inject(ChatService);
  readonly live = isFullyLive();
  readonly policy = toSignal(this.api.getPolicy());
  readonly claim = toSignal(this.api.getCase());
  readonly session = toSignal(this.api.getSessionInfo().pipe(catchError(() => of(null))));
  readonly ready = computed(() => this.policy() !== undefined && this.claim() !== undefined && !!this.session());
  readonly hasDocuments = computed(() => !!this.policy() || !!this.claim()?.documents?.length);
  readonly demoContext = computed(() => this.session()?.mode === 'live_demo');
  readonly prompts = computed(() => this.hasDocuments() && this.live
    ? ['What is my room-rent limit?', 'Why was money deducted from my claim?', 'Which documents am I missing?']
    : ['What is a waiting period?', 'How do I question a deduction?']);
  readonly demoLoading = signal(false);
  readonly demoError = signal<string | null>(null);
  readonly demoBlocked = signal(false);

  loadDemo(): void {
    this.demoError.set(null);
    if (!this.live) {
      this.demoError.set('Enable live features in Demo and session settings before loading the live AI demo.');
      this.demoBlocked.set(true);
      return;
    }
    if (!this.ready()) return;
    if (this.demoContext()) { void this.router.navigateByUrl('/case'); return; }
    if (this.hasDocuments()) {
      this.demoBlocked.set(true);
      this.demoError.set('This guest session already has documents. Loading the demo can change your selected policy and claim. Review the demo/session settings first.');
      return;
    }
    this.demoLoading.set(true);
    this.api.loadDemoCase().subscribe({
      next: () => { this.demoLoading.set(false); void this.router.navigateByUrl('/case'); },
      error: (error) => {
        this.demoLoading.set(false);
        this.demoError.set(error?.error?.detail ?? 'Could not load the demo. Please retry.');
      },
    });
  }
}
