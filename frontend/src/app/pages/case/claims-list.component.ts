import { Component, computed, inject, signal } from '@angular/core';
import { formatDate } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService, isLive } from '../../services/api.service';
import { ClaimSwitchService } from '../../services/claim-switch.service';
import { ClaimStatus, ClaimSummary, PastClaimInput } from '../../models/models';
import { todayIso } from '../../shared/claim-diary';
import { InrPipe } from '../../shared/inr.pipe';
import { TranslatePipe } from '../../shared/translate.pipe';

type ClaimFilter = 'all' | 'pending_reply' | 'in_progress' | 'closed';

const STATUS: Record<ClaimStatus, { label: string; icon: string; tone: string }> = {
  in_progress: { label: 'Waiting for a decision', icon: 'hourglass_top', tone: 'info' },
  paid: { label: 'Approved', icon: 'task_alt', tone: 'ok' },
  part_paid: { label: 'Partially approved', icon: 'content_cut', tone: 'warn' },
  refused: { label: 'Refused', icon: 'cancel', tone: 'bad' },
};

interface Draft { title: string; patient: string; hospital: string; date: string; claimed: number | null; paid: number | null; claimNumber: string }

const EMPTY_DRAFT: Draft = { title: '', patient: '', hospital: '', date: '', claimed: null, paid: null, claimNumber: '' };

/** Every claim on the policy: the one open on this page, earlier ones kept in CareNest, and past claims typed in. */
@Component({
  selector: 'app-claims-list',
  standalone: true,
  imports: [FormsModule, RouterLink, MatButtonModule, MatIconModule, InrPipe, TranslatePipe],
  template: `
    <section class="card" id="claims" aria-labelledby="claims-title">
      <div class="cl-head">
        <div>
          <h2 id="claims-title">{{ 'Your claims' | t }}</h2>
          <p class="muted small">{{ 'Every claim on this policy, newest first. What the insurer paid this policy year lowers the cover you have left.' | t }}</p>
        </div>
        @if (switcher.canStartNew()) {
          <button mat-stroked-button class="btn-ink" type="button" (click)="switcher.startNew()" [disabled]="switcher.busy()"><mat-icon>add</mat-icon> {{ 'Start a new claim' | t }}</button>
        }
      </div>

      @if (claims(); as list) {
        @if (list.length && !switcher.canStartNew()) {
          <p class="cl-new"><mat-icon>fiber_new</mat-icon><span>{{ 'A new claim is open. Add the hospital bill to start it.' | t }} <a routerLink="/upload" [queryParams]="{ type: 'Hospital bill' }">{{ 'Add the hospital bill' | t }}</a></span></p>
        }
        <div class="cl-filters" role="group" aria-label="Filter claims">
          @for (tab of filters; track tab.key) {
            <button type="button" class="cl-filter" [class.selected]="filter() === tab.key"
              [attr.aria-pressed]="filter() === tab.key" (click)="filter.set(tab.key)">
              {{ tab.label | t }} <span class="cl-count">{{ count(tab.key) }}</span>
            </button>
          }
        </div>
        <p class="cl-result muted small" role="status">{{ visibleClaims().length }} {{ 'of' | t }} {{ list.length }} {{ 'claims' | t }}</p>
        <ul class="cl-list">
          @for (c of visibleClaims(); track c.id) {
            <li class="cl-row" [class.current]="c.current">
              <span [class]="'cl-icon tone-' + status(c).tone"><mat-icon>{{ status(c).icon }}</mat-icon></span>
              <div class="cl-main">
                <div class="cl-title">
                  @if (c.current || switcher.canOpen(c)) {
                    <button class="cl-open-title" type="button" (click)="switcher.open(c)" [disabled]="switcher.busy()" [attr.aria-label]="'View claim: ' + c.title">{{ c.title }}</button>
                  } @else { <strong>{{ c.title }}</strong> }
                  @if (c.current) { <span class="pill tone-info">{{ 'Selected claim' | t }}</span> }
                  @if (c.source === 'manual') { <span class="pill cl-manual">{{ 'Added by you' | t }}</span> }
                </div>
                <div class="cl-meta muted small">
                  @for (d of details(c); track $index) { <span [class.cl-keep]="d.keep">{{ d.text }}</span> }
                </div>
              </div>
              <div class="cl-money">
                @if (c.approvedAmount !== null) {
                  <span><strong>{{ c.approvedAmount | inr }}</strong><span class="cl-paid muted small">{{ 'approved' | t }}</span></span>
                  @if (c.claimedAmount) { <span class="muted small">{{ 'Claimed' | t }} {{ c.claimedAmount | inr }}</span> }
                }
                <span [class]="'pill tone-' + status(c).tone">{{ status(c).label | t }}</span>
              </div>
              <div class="cl-actions">
                  @if (c.current || switcher.canOpen(c)) {
                    <button mat-button type="button" (click)="switcher.open(c)" [disabled]="switcher.busy()" [attr.aria-label]="('Open' | t) + ': ' + c.title">{{ 'Open' | t }}</button>
                  }
                  @if (switcher.canDelete(c)) {
                    <button mat-icon-button type="button" (click)="switcher.remove(c)" [disabled]="switcher.busy()" [attr.aria-label]="('Delete claim' | t) + ': ' + c.title"><mat-icon>delete</mat-icon></button>
                  }
                </div>
            </li>
          } @empty {
            <li class="cl-empty small">{{ (list.length ? 'No claims in this section.' : 'No claims yet. Upload a hospital bill to start one, or add a claim you made before.') | t }}</li>
          }
        </ul>
      } @else if (claims() === null) {
        <p class="small">{{ "We couldn't load your claims." | t }}</p>
      }

      @if (!live) {
        <p class="muted small">{{ 'Demo: a new claim stays empty, because uploads in the demo are not saved. Open the sample claim from this list to go back to it.' | t }}</p>
      }

      @if (adding()) {
        <form class="cl-form" (ngSubmit)="save()">
          <h3>{{ 'Add a past claim' | t }}</h3>
          <p class="muted small">{{ "Copy these from the insurer's payment letter. Only the date and the amount paid are needed." | t }}</p>
          <div class="cl-fields">
            <label>{{ 'Discharge date' | t }} *
              <input type="date" name="date" required [max]="today" [(ngModel)]="draft.date">
            </label>
            <label>{{ 'Amount the insurer paid (₹)' | t }} *
              <input type="number" name="paid" required min="0" step="100" [(ngModel)]="draft.paid" aria-describedby="cl-paid-hint">
              <span class="cl-hint" id="cl-paid-hint">{{ 'Enter 0 if the claim was refused.' | t }}</span>
            </label>
            <label>{{ 'Amount claimed (₹)' | t }}
              <input type="number" name="claimed" min="1" step="100" [(ngModel)]="draft.claimed">
            </label>
            <label>{{ 'What it was for' | t }}
              <input type="text" name="title" maxlength="80" [(ngModel)]="draft.title" autocomplete="off">
            </label>
            <label>{{ 'Patient' | t }}
              <input type="text" name="patient" maxlength="60" [(ngModel)]="draft.patient" autocomplete="off">
            </label>
            <label>{{ 'Hospital' | t }}
              <input type="text" name="hospital" maxlength="80" [(ngModel)]="draft.hospital" autocomplete="off">
            </label>
            <label>{{ 'Claim number' | t }}
              <input type="text" name="claimNumber" maxlength="40" [(ngModel)]="draft.claimNumber" autocomplete="off">
            </label>
          </div>
          @if (error(); as err) { <p class="cl-error" role="alert">{{ err | t }}</p> }
          <div class="row">
            <button mat-flat-button type="submit" [disabled]="switcher.busy()">{{ 'Add claim' | t }}</button>
            <button mat-button type="button" (click)="adding.set(false)">{{ 'Cancel' | t }}</button>
          </div>
        </form>
      } @else {
        <button mat-button type="button" class="cl-add btn-violet" (click)="startAdding()"><mat-icon>playlist_add</mat-icon> {{ 'Add a past claim' | t }}</button>
      }
    </section>
  `,
  styles: `
    .cl-head { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 8px 16px; }
    .cl-head h2 { margin: 0; }
    .cl-head p { margin: 4px 0 0; }
    .cl-filters { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--cn-border); }
    .cl-filter { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; padding: 8px 14px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: var(--cn-muted); font: inherit; cursor: pointer; }
    .cl-filter.selected { color: var(--cn-strong); background: var(--cn-c1-soft); border-color: var(--cn-border); font-weight: 700; }
    .cl-filter:focus-visible { outline: 2px solid var(--cn-strong); outline-offset: 2px; }
    .cl-count { font-size: .8em; min-width: 1.2em; text-align: center; }
    .cl-result { margin: 8px 0 0; }
    .cl-list { list-style: none; margin: 12px 0 8px; padding: 0; display: grid; gap: 8px; }
    .cl-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; align-items: center; gap: 8px 14px; padding: 12px 14px;
              border: 1px solid var(--cn-border); border-radius: var(--cn-radius); background: var(--cn-surface); }
    .cl-row.current { border-color: var(--cn-c2-line); background: linear-gradient(135deg, var(--cn-c2-soft), var(--cn-surface) 75%); }
    .cl-icon { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; }
    .cl-main { min-width: 0; }
    .cl-title { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
    .cl-open-title { color: var(--cn-strong); font: inherit; font-weight: 700; border: 0; background: none; text-align: left; padding: 0; min-height: 44px; cursor: pointer; }
    .cl-open-title:hover { text-decoration: underline; }
    .cl-open-title:focus-visible { outline: 2px solid var(--cn-strong); outline-offset: 2px; }
    .cl-title strong { color: var(--cn-strong); }
    .cl-manual { background: var(--cn-c5-soft); color: var(--cn-c5-ink); }
    .cl-meta span:not(:last-child)::after { content: '·'; margin: 0 .4em; }
    .cl-keep { display: inline-block; white-space: nowrap; }
    .cl-money { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; text-align: right; font-variant-numeric: tabular-nums; }
    .cl-money strong { color: var(--cn-strong); }
    .cl-paid { margin-left: .3em; }
    .cl-actions { display: flex; align-items: center; }
    .cl-new { display: flex; align-items: center; gap: 10px; margin: 12px 0 0; padding: 10px 14px; border-radius: 12px;
              background: var(--cn-c3-soft); color: var(--cn-c3-ink); font-size: .9rem; }
    .cl-new a { color: inherit; font-weight: 700; }
    .cl-empty { padding: 8px 0; }
    .cl-form { margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--cn-border-strong); }
    .cl-form h3 { margin: 0 0 4px; }
    .cl-fields { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin: 12px 0; }
    .cl-fields label { display: flex; flex-direction: column; gap: 4px; font-size: .85rem; color: var(--cn-muted); }
    .cl-fields input { min-height: 44px; padding: 0 10px; font: inherit; font-size: 1rem; color: var(--cn-ink); border: 1px solid var(--cn-border);
                       border-radius: 10px; background: var(--cn-field); min-width: 0; }
    .cl-hint { font-size: .78rem; }
    .cl-error { color: var(--cn-bad); }
    .cl-add { margin-top: 4px; }
    @media (max-width: 599px) {
      .cl-row { grid-template-columns: auto minmax(0, 1fr) auto; align-items: start; padding: 12px; gap: 8px 12px; }
      .cl-icon { width: 36px; height: 36px; border-radius: 10px; }
      .cl-money { grid-column: 2 / 4; grid-row: 2; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 4px 10px; text-align: left; }
      .cl-actions { grid-column: 3; grid-row: 1; margin: -6px -6px 0 0; }
    }
  `,
})
export class ClaimsListComponent {
  private api = inject(ApiService);
  readonly switcher = inject(ClaimSwitchService);

  readonly live = isLive('case');
  readonly today = todayIso();
  readonly claims = this.switcher.claims;
  readonly filter = signal<ClaimFilter>('all');
  readonly filters: {key: ClaimFilter; label: string}[] = [
    {key: 'all', label: 'All claims'}, {key: 'pending_reply', label: 'Pending reply'},
    {key: 'in_progress', label: 'In progress'}, {key: 'closed', label: 'Closed'},
  ];
  readonly visibleClaims = computed(() => (this.claims() ?? []).filter(c => this.matches(c, this.filter())));
  count(filter: ClaimFilter): number { return (this.claims() ?? []).filter(c => this.matches(c, filter)).length; }
  private matches(c: ClaimSummary, filter: ClaimFilter): boolean {
    if (filter === 'all') return true;
    if (filter === 'closed') return c.closed;
    if (filter === 'pending_reply') return !c.closed && !!c.awaitingReply;
    return !c.closed && !c.awaitingReply;
  }
  readonly adding = signal(false);
  readonly error = signal<string | null>(null);
  draft: Draft = { ...EMPTY_DRAFT };

  status(c: ClaimSummary) {
    return STATUS[c.status];
  }

  /** Patient and hospital may wrap; the date and claim number stay on one line. */
  details(c: ClaimSummary): { text: string; keep: boolean }[] {
    const when = /^\d{4}-\d{2}-\d{2}$/.test(c.date) ? formatDate(c.date, 'd MMM y', 'en-US') : '';
    return [{ text: c.patient, keep: false }, { text: c.hospital, keep: false }, { text: when, keep: true }, { text: c.claimNumber, keep: true }]
      .filter((d) => d.text);
  }

  startAdding(): void {
    this.draft = { ...EMPTY_DRAFT };
    this.error.set(null);
    this.adding.set(true);
  }

  save(): void {
    const d = this.draft;
    if (!d.date || d.date > this.today) return this.error.set('Enter the discharge date (not in the future).');
    if (d.paid === null || d.paid < 0) return this.error.set('Enter the amount the insurer paid (0 if refused).');
    if (d.claimed !== null && d.claimed > 0 && d.paid > d.claimed) return this.error.set('The amount paid cannot be more than the amount claimed.');
    const input: PastClaimInput = {
      date: d.date,
      approvedAmount: d.paid,
      ...(d.claimed && d.claimed > 0 ? { claimedAmount: d.claimed } : {}),
      ...(d.title.trim() ? { title: d.title.trim() } : {}),
      ...(d.patient.trim() ? { patient: d.patient.trim() } : {}),
      ...(d.hospital.trim() ? { hospital: d.hospital.trim() } : {}),
      ...(d.claimNumber.trim() ? { claimNumber: d.claimNumber.trim() } : {}),
    };
    this.error.set(null);
    this.switcher.run(this.api.addPastClaim(input), () => this.adding.set(false));
  }
}
