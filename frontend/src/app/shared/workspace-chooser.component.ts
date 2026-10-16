import { Component, inject, signal } from '@angular/core';
import { A11yModule } from '@angular/cdk/a11y';
import { MatIconModule } from '@angular/material/icon';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { WorkspaceService, DocumentWorkspace } from '../services/workspace.service';
import { ApiService } from '../services/api.service';
import { ChatService } from '../services/chat.service';

@Component({ selector: 'app-workspace-chooser', standalone: true, imports: [A11yModule, MatIconModule],
  template: `@if (workspace.choosing()) {
    <div class="workspace-overlay">
      <section class="workspace-dialog" role="dialog" aria-modal="true" aria-labelledby="workspace-title" (keydown.escape)="!busy() && chat.cancelChoice()" cdkTrapFocus [cdkTrapFocusAutoCapture]="true">
        <button class="dialog-close" type="button" aria-label="Close workspace choice" (click)="chat.cancelChoice()" [disabled]="busy()"><mat-icon>close</mat-icon></button>
        <p class="eyebrow">YOUR CONVERSATION, YOUR CONTEXT</p>
        <h2 id="workspace-title">How would you like to use CareNest?</h2>
        <p>Nessi will use only the documents in the space you choose. You can switch at any time.</p>
        <button class="workspace-option" type="button" (click)="choose('example')" [disabled]="busy()" cdkFocusInitial>
          <mat-icon>account_circle</mat-icon><span><strong>Try as Shubham</strong><small>A fictional family's policy, bill and claim. Everything is ready to explore.</small></span><mat-icon>arrow_forward</mat-icon>
        </button>
        <button class="workspace-option" type="button" (click)="choose('personal')" [disabled]="busy()">
          <mat-icon>folder_open</mat-icon><span><strong>Use my own documents</strong><small>Ask general questions now. Add your policy, bills or letters when needed.</small></span><mat-icon>arrow_forward</mat-icon>
        </button>
        @if (busy()) { <p role="status">Opening your workspace…</p> }
        @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
        <p class="small muted">No sign-in. Both spaces stay separate in this browser session; switching does not delete your work.</p>
      </section>
    </div>
  }`,
})
export class WorkspaceChooserComponent {
  readonly workspace = inject(WorkspaceService);
  readonly chat = inject(ChatService);
  private api = inject(ApiService);
  private router = inject(Router);
  readonly busy = signal(false);
  readonly error = signal('');
  async choose(mode: DocumentWorkspace): Promise<void> {
    const previous = this.workspace.mode();
    this.busy.set(true); this.error.set('');
    try {
      await firstValueFrom(this.api.activateWorkspace(mode));
      this.workspace.select(mode);
      const url = this.router.parseUrl(this.router.url);
      if (url.root.children['primary']?.segments[0]?.path === 'upload' && mode === 'example') {
        await this.router.navigate(['/dashboard'], { queryParams: { workspace: mode } });
      } else {
        url.queryParams['workspace'] = mode;
        await this.router.navigateByUrl(url, { onSameUrlNavigation: 'reload' });
      }
      this.workspace.choosing.set(false);
      this.chat.resumeAfterChoice();
    } catch {
      this.api.clearWorkspace();
      await firstValueFrom(this.api.activateWorkspace(previous)).catch(() => undefined);
      this.error.set('Could not open this workspace. Please try again.');
    } finally { this.busy.set(false); }
  }
}
