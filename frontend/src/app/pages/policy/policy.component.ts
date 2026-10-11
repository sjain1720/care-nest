import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { WaitingPeriod } from '../../models/models';
import { InrPipe } from '../../shared/inr.pipe';
import { CitationChipComponent } from '../../shared/citation-chip.component';
import { TrustPillComponent } from '../../shared/trust-pill.component';

interface TimelineRow extends WaitingPeriod {
  offsetPct: number;
  widthPct: number;
  over: boolean;
}

const FLAG_ICONS: Record<string, string> = { missing_pages: 'find_in_page', outdated: 'history', ambiguous: 'help_center' };

@Component({
  selector: 'app-policy',
  standalone: true,
  imports: [DatePipe, RouterLink, MatButtonModule, MatIconModule, InrPipe, CitationChipComponent, TrustPillComponent],
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
    .today-label { position: absolute; top: -22px; transform: translateX(-50%); font-size: .7rem; font-weight: 600; white-space: nowrap; }
    .flag { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; }
    .flag mat-icon { color: var(--cn-warn); flex: none; }
  `,
})
export class PolicyComponent {
  private api = inject(ApiService);
  policy = toSignal(this.api.getPolicy());
  readonly today = new Date();

  timeline = computed(() => {
    const p = this.policy();
    if (!p) return null;
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
}
