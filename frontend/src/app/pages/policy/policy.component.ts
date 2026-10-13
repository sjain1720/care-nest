import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { Citation, PolicyFacts, WaitingPeriod } from '../../models/models';
import { InrPipe, formatInr } from '../../shared/inr.pipe';
import { NextStep, NextStepsComponent } from '../../shared/next-steps.component';
import { EmptyStateComponent, SkeletonComponent } from '../../shared/page-states.component';
import { GlossComponent } from '../../shared/gloss.component';
import { CitationChipComponent } from '../../shared/citation-chip.component';
import { TrustPillComponent } from '../../shared/trust-pill.component';
import { RoomRentSimulatorComponent } from '../../shared/room-rent-simulator.component';
import { PolicyDetailsFormComponent } from './policy-details-form.component';
import { CoverageEstimateComponent } from '../../shared/coverage-estimate.component';

interface TimelineRow extends WaitingPeriod {
  offsetPct: number;
  widthPct: number;
  over: boolean;
}

const FLAG_ICONS: Record<string, string> = { missing_pages: 'find_in_page', outdated: 'history', ambiguous: 'help_center' };

@Component({
  selector: 'app-policy',
  standalone: true,
  imports: [DatePipe, RouterLink, MatButtonModule, MatIconModule, InrPipe, CitationChipComponent, TrustPillComponent, TranslatePipe,
            RoomRentSimulatorComponent, PolicyDetailsFormComponent, NextStepsComponent, SkeletonComponent, EmptyStateComponent, GlossComponent,
            CoverageEstimateComponent],
  templateUrl: './policy.component.html',
  styles: `
    .members { display: flex; flex-wrap: wrap; gap: 8px; }
    .member { background: var(--cn-bg); border-radius: 10px; padding: 6px 12px; font-size: .9rem; }
    .limits li { margin-bottom: 10px; }
    .limits { padding-left: 20px; margin: 0; }
    .trap { border-left: 4px solid var(--cn-warn); }
    .trap p { margin: 6px 0 10px; color: var(--cn-muted); }
    .timeline { position: relative; margin-top: 8px; }
    .tl-row { margin-bottom: 14px; }
    .tl-head { display: flex; justify-content: space-between; gap: 8px; font-size: .9rem; margin-bottom: 4px; flex-wrap: wrap; }
    .track { position: relative; height: 12px; background: var(--cn-bg); border-radius: 999px; }
    .bar { position: absolute; top: 0; bottom: 0; border-radius: 999px; background: var(--cn-warn); }
    .bar.over { background: var(--cn-ok); }
    .today { position: absolute; top: -6px; bottom: -6px; width: 2px; background: var(--cn-ink); }
    .today-label { position: absolute; top: -24px; transform: translateX(-50%); padding: 1px 8px; border-radius: 999px; font-size: .75rem; font-weight: 700;
                   white-space: nowrap; color: var(--cn-surface); background: var(--cn-ink); }
    .flag { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; }
    .flag mat-icon { color: var(--cn-warn); flex: none; }
    .notice { display: flex; gap: 12px; align-items: flex-start; border-left: 4px solid var(--cn-warn); background: var(--cn-warn-soft); }
    .notice mat-icon { color: var(--cn-warn); flex: none; }
    .notice p { margin: 4px 0 8px; }
    .by-you { font-size: .78rem; font-weight: 600; color: var(--cn-primary); }
  `,
})
export class PolicyComponent {
  private api = inject(ApiService);
  /** undefined = loading, null = no policy uploaded yet. */
  policy = signal<PolicyFacts | null | undefined>(undefined);
  editing = signal(false);
  readonly today = new Date();

  missingStartDate = computed(() => !!this.policy()?.flags.some((f) => f.code === 'missing_start_date'));

  nextSteps = computed<NextStep[]>(() => {
    const p = this.policy();
    if (!p) return [];
    const steps: NextStep[] = [];
    // A missing start date already has its own notice above this card.
    if (!this.missingStartDate() && !p.sumInsured) {
      steps.push({ text: 'Add your cover amount. It is on your policy schedule (the page with your name).', action: 'Add details', route: '/policy', fragment: 'details' });
    }
    if (p.roomRent.amount) {
      steps.push({ text: `Planning a hospital stay? Pick a room that costs ${formatInr(p.roomRent.amount)} a day or less.`, action: 'Check a room', route: '/policy', fragment: 'room-rent' });
    }
    const waiting = (this.timeline()?.rows ?? []).filter((w) => !w.over);
    if (waiting.length) {
      steps.push({ text: `${waiting.length} kind${waiting.length === 1 ? ' of treatment is' : 's of treatment are'} not covered yet. See when cover starts.`, action: 'See dates', route: '/policy', fragment: 'waiting-periods' });
    }
    steps.push({ text: 'Read the traps below. They are the most common reasons claims get cut.', action: 'See traps', route: '/policy', fragment: 'traps' });
    steps.push({ text: 'Not sure if a treatment is covered? Ask us in your own words.', action: 'Ask', ask: "Is my father's cataract surgery covered?" });
    return steps;
  });

  constructor() {
    this.api.getPolicy().pipe(takeUntilDestroyed()).subscribe((p) => this.policy.set(p));
  }

  byYou(field: string): boolean {
    return !!this.policy()?.userProvided?.includes(field);
  }

  onSaved(facts: PolicyFacts): void {
    this.policy.set(facts);
    this.editing.set(false);
  }

  timeline = computed(() => {
    const p = this.policy();
    if (!p || !p.startDate || !p.waitingPeriods.length) return null;
    const start = Date.parse(p.startDate);
    const end = Math.max(...p.waitingPeriods.map((w) => Date.parse(w.endDate)), this.today.getTime());
    const span = end - start || 1;
    const pct = (t: number) => Math.min(100, Math.max(0, ((t - start) / span) * 100));
    const rows: TimelineRow[] = p.waitingPeriods.map((w) => ({
      ...w,
      offsetPct: pct(Date.parse(w.startDate)),
      widthPct: pct(Date.parse(w.endDate)) - pct(Date.parse(w.startDate)),
      over: Date.parse(w.endDate) <= this.today.getTime(),
    }));
    return { rows, todayPct: pct(this.today.getTime()) };
  });

  flagIcon(kind: string): string {
    return FLAG_ICONS[kind] ?? 'flag';
  }

  roomRentCitations(): Citation[] {
    const p = this.policy();
    if (!p) return [];
    const fromTraps = p.traps.map((t) => t.citation).filter((c) => c.clause === 'Clause 5.3');
    return [...(p.roomRent.citation ? [p.roomRent.citation] : []), ...fromTraps.slice(0, 1)];
  }
}
