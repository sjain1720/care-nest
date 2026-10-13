import { Component, computed, inject, input } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { ApiService, isLive } from '../services/api.service';
import { ClaimSummary } from '../models/models';
import { todayIso } from './claim-diary';
import { InrPipe } from './inr.pipe';
import { TranslatePipe } from './translate.pipe';

/** The policy year that contains today, counted from the start date's anniversary; null without a start date. */
function policyYear(start: string | undefined, today: string): { from: string; to: string } | null {
  if (!start || !/^\d{4}-\d{2}-\d{2}$/.test(start)) return null;
  const [y, m, d] = start.split('-').map(Number);
  const thisYear = Number(today.slice(0, 4));
  const from = Math.max(y, `${thisYear}${start.slice(4)}` <= today ? thisYear : thisYear - 1);
  const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
  return { from: iso(Date.UTC(from, m - 1, d)), to: iso(Date.UTC(from + 1, m - 1, d - 1)) };
}

/**
 * "Estimated coverage remaining" = sum insured − what the insurer paid on the claims in this policy year.
 * Plain arithmetic in code (never from the AI), labelled as an estimate with its assumptions shown.
 */
@Component({
  selector: 'app-coverage-estimate',
  standalone: true,
  imports: [DatePipe, RouterLink, MatIconModule, InrPipe, TranslatePipe],
  template: `
    <section class="card cov" [class.compact]="compact()" id="coverage" aria-labelledby="cov-title">
      <div class="cov-head">
        <span class="cov-icon"><mat-icon>savings</mat-icon></span>
        <div class="cov-titles">
          <h2 id="cov-title">{{ 'Estimated coverage remaining' | t }}</h2>
          <span class="cov-basis">
            @if (estimate()?.year; as y) { {{ 'Policy year' | t }} {{ y.from | date: 'd MMM y' }} – {{ y.to | date: 'd MMM y' }} }
            @else { {{ 'Based on your claims list' | t }} }
            @if (demo) { · {{ 'Demo data' | t }} }
          </span>
        </div>
      </div>
      @if (estimate(); as e) {
        <div class="cov-main">
          <strong class="cov-left">{{ e.remaining | inr }}</strong>
          <span class="cov-pct">{{ e.pct }}% {{ 'left' | t }}</span>
        </div>
        <div class="cov-bar" role="img" [attr.aria-label]="e.pct + '% ' + ('left' | t)"><span [style.width.%]="e.pct"></span></div>
        <dl class="cov-rows">
          <div><dt>{{ 'Sum insured' | t }}</dt><dd>{{ e.sumInsured | inr }}</dd></div>
          @if (compact() || !e.counted.length) {
            <div><dt>{{ (e.year ? 'Claims paid this policy year' : 'Claims paid') | t }} ({{ e.counted.length }})</dt><dd class="used">− {{ e.used | inr }}</dd></div>
          } @else {
            @for (c of e.counted; track c.id) {
              <div><dt>{{ c.title }} <span class="cov-date">· {{ c.date | date: 'd MMM y' }}</span></dt><dd class="used">− {{ c.approvedAmount | inr }}</dd></div>
            }
          }
          <div class="tot"><dt>{{ 'Estimated remaining' | t }}</dt><dd>{{ e.remaining | inr }}</dd></div>
        </dl>
        @if (compact()) {
          <a class="cov-more" routerLink="/policy" fragment="coverage">{{ 'How this is worked out' | t }}<mat-icon>arrow_forward</mat-icon></a>
        } @else {
          <h3 class="cov-sub">{{ 'What this estimate assumes' | t }}</h3>
          <ul class="cov-assume">
            <li>{{ 'Only the claims in your claims list are counted. Add any claim made outside CareNest to' | t }} <a routerLink="/case" fragment="claims">{{ 'your claims list' | t }}</a>.</li>
            @if (e.year) {
              <li>{{ 'Only claims in the current policy year are counted, because the cover starts again each policy year.' | t }}</li>
            } @else {
              <li>{{ 'Add your policy start date to count only the current policy year.' | t }}</li>
            }
            @if (e.pending) { <li>{{ 'A claim the insurer has not decided yet is not counted.' | t }}</li> }
            @if (e.floater) { <li>{{ 'Family floater: everyone on the policy shares this one amount.' | t }}</li> }
            <li>{{ 'Restoration (refill) benefits, sub-limits, co-pay and deductibles can change the real figure.' | t }}</li>
            <li>{{ "This is not the insurer's official balance. Ask the insurer or TPA to confirm it." | t }}</li>
          </ul>
        }
      } @else if (ready()) {
        <p class="muted small">{{ 'Add the sum insured from your policy schedule to see an estimate.' | t }}</p>
        <a class="cov-more" routerLink="/policy" fragment="details">{{ 'Add it' | t }}<mat-icon>arrow_forward</mat-icon></a>
      }
    </section>
  `,
  styles: `
    .cov { background: linear-gradient(135deg, var(--cn-c1-soft), var(--cn-surface) 70%); border-color: var(--cn-c1-line); }
    .cov-head { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
    .cov-icon { flex: none; width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; background: var(--cn-c1-soft); color: var(--cn-c1-ink); }
    .cov-titles { display: flex; flex-direction: column; min-width: 0; }
    .cov-titles h2 { margin: 0; font-size: 1.05rem; }
    .cov-basis { font-size: .8rem; color: var(--cn-muted); }
    .cov-main { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; }
    .cov-left { font-size: 2rem; font-weight: 800; color: var(--cn-c1-ink); font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
    .cov-pct { padding: 2px 10px; border-radius: 999px; font-size: .8rem; font-weight: 700; background: var(--cn-c1-soft); color: var(--cn-c1-ink); }
    .cov-bar { height: 10px; margin: 10px 0 14px; border-radius: 999px; background: var(--cn-track); overflow: hidden; }
    .cov-bar span { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--cn-c1), var(--cn-c6)); }
    .cov-rows { display: grid; gap: 6px; margin: 0; }
    .cov-rows div { display: flex; justify-content: space-between; gap: 12px; font-size: .9rem; }
    .cov-rows dt { color: var(--cn-muted); }
    .cov-date { white-space: nowrap; font-size: .82rem; }
    .cov-rows dd { margin: 0; font-weight: 700; color: var(--cn-strong); font-variant-numeric: tabular-nums; }
    .cov-rows dd.used { color: var(--cn-c4-ink); }
    .cov-rows .tot { padding-top: 6px; border-top: 1px dashed var(--cn-border-strong); }
    .cov-rows .tot dd { color: var(--cn-c1-ink); }
    .cov-more { display: inline-flex; align-items: center; gap: 4px; margin-top: 12px; min-height: 32px; font-size: .88rem; font-weight: 600; color: var(--cn-link); text-decoration: none; }
    .cov-more mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .cov-more:hover { text-decoration: underline; }
    .cov-sub { margin: 16px 0 6px; font-size: .9rem; }
    .cov-assume { margin: 0; padding-left: 18px; font-size: .86rem; color: var(--cn-muted); }
    .cov-assume li { margin: 2px 0; }
    @media (prefers-reduced-motion: no-preference) {
      .cov-bar span { animation: cov-grow .9s var(--cn-ease) .2s backwards; transform-origin: left; }
    }
    @keyframes cov-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  `,
})
export class CoverageEstimateComponent {
  /** Dashboard: short version with a link to the full one on the policy page. */
  readonly compact = input(false);
  private api = inject(ApiService);
  private policy = toSignal(this.api.getPolicy());
  private claims = toSignal(this.api.getClaims());
  readonly demo = !isLive('policy');
  readonly ready = computed(() => this.policy() !== undefined && this.claims() !== undefined);

  readonly estimate = computed(() => {
    const p = this.policy();
    if (!p?.sumInsured || this.claims() === undefined) return null;
    const claims: ClaimSummary[] = this.claims() ?? [];
    const year = policyYear(p.startDate, todayIso());
    const inYear = (c: ClaimSummary) => !year || !c.date || (c.date >= year.from && c.date <= year.to);
    const counted = claims.filter((c) => !!c.approvedAmount && inYear(c));
    const used = Math.min(counted.reduce((sum, c) => sum + (c.approvedAmount ?? 0), 0), p.sumInsured);
    const remaining = p.sumInsured - used;
    return {
      sumInsured: p.sumInsured, used, remaining, counted, year,
      pct: Math.round((remaining / p.sumInsured) * 100),
      pending: claims.some((c) => c.approvedAmount === null),
      floater: /floater/i.test(p.policyType ?? ''),
    };
  });
}
