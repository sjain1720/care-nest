import { Injectable, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Observable } from 'rxjs';
import { ApiService, DEMO_CLAIM_ID, isLive } from './api.service';
import { ClaimSummary } from '../models/models';
import { TranslatePipe } from '../shared/translate.pipe';

/** Starting a new claim and switching between claims, shared by the dashboard, My claim and the claims list. */
@Injectable({ providedIn: 'root' })
export class ClaimSwitchService {
  private api = inject(ApiService);
  private router = inject(Router);
  private snackBar = inject(MatSnackBar);
  private translate = new TranslatePipe();

  readonly claims = toSignal(this.api.getClaims());
  /** The open claim has something in it; an empty one is already a new claim. */
  readonly canStartNew = computed(() => !!this.claims()?.some((c) => c.current));
  readonly busy = signal(false);

  canOpen(c: ClaimSummary): boolean {
    return !c.current && c.source === 'carenest' && (isLive('case') || c.id === DEMO_CLAIM_ID);
  }

  canDelete(c: ClaimSummary): boolean {
    return !c.current && c.id !== DEMO_CLAIM_ID;
  }

  startNew(): void {
    if (!confirm(this.t('Start a new claim? This claim stays in your list, and you can open it again.'))) return;
    this.run(this.api.startNewClaim(), () => {
      this.details();
      scrollTo({ top: 0 });
      this.snackBar.open(this.t('New claim started. Add the hospital bill to begin.'), this.t('Add the bill'), { duration: 8000 })
        .onAction().subscribe(() => this.router.navigate(['/upload']));
    });
  }

  open(c: ClaimSummary): void {
    if (c.current) { this.details(); return; }
    this.run(this.api.openClaim(c.id), () => {
      scrollTo({ top: 0 });
      this.details();
      this.snackBar.open(`${this.t('Opened')}: ${c.title}`, undefined, { duration: 4000 });
    });
  }

  private details(): void {
    void this.router.navigate(['/case/detail'], {queryParams: {workspace: this.api.workspace.mode()}});
  }

  remove(c: ClaimSummary): void {
    if (!confirm(`${this.t('Delete this claim and its files from CareNest? This cannot be undone.')}\n\n${c.title}`)) return;
    this.run(this.api.deleteClaim(c.id));
  }

  run(action: Observable<unknown>, done?: () => void): void {
    this.busy.set(true);
    action.subscribe({
      next: () => {
        this.busy.set(false);
        done?.();
      },
      error: () => this.busy.set(false),
    });
  }

  private t(text: string): string {
    return this.translate.transform(text);
  }
}
