import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { ApiService, isLive } from '../../services/api.service';
import { ChatService } from '../../services/chat.service';
import { JourneyService } from '../../services/journey.service';
import { InrPipe, formatInr } from '../../shared/inr.pipe';
import { TranslatePipe } from '../../shared/translate.pipe';
import { shortDate, eventText } from '../../shared/claim-diary';
import { CountUpDirective } from '../../shared/count-up.directive';
import { ChatBarComponent } from '../../shared/chat-bar.component';
import { CoverageEstimateComponent } from '../../shared/coverage-estimate.component';
import { TimelineEvent } from '../../models/models';

interface Tip {
  icon: string;
  title: string;
  text: string;
  /** Only for links the dashboard doesn't already have as a tile. */
  action?: string;
  route?: string;
  fragment?: string;
  ask?: string;
}

interface Service {
  icon: string;
  label: string;
  route: string;
  fragment?: string;
}

/** One box in the summary row (like From / To / Date on a travel site). */
interface HeroField {
  label: string;
  value: string;
  /** Rupee amount that counts up from 0. */
  amount?: number;
  /** Share paid, drawn as a small ring. */
  donut?: number;
  sub: string;
  tone?: 'ok' | 'bad';
  /** Spans two columns on phones. */
  wide?: boolean;
  route: string;
  fragment?: string;
}

interface Attention {
  tone: 'bad' | 'warn' | 'unknown' | 'ok' | 'info';
  icon: string;
  title: string;
  text: string;
  route: string;
  fragment?: string;
  query?: Record<string, string>;
}

interface WaitRow {
  id: string;
  label: string;
  endDate: string;
  over: boolean;
  pct: number;
  left: string;
}

const DAY = 86_400_000;

function timeLeft(days: number): string {
  if (days < 45) return `${days} day${days === 1 ? '' : 's'} left`;
  const months = Math.round(days / 30.4);
  return months < 18 ? `${months} months left` : `${(months / 12).toFixed(1).replace('.0', '')} years left`;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [DatePipe, NgTemplateOutlet, RouterLink, MatButtonModule, MatIconModule, MatProgressBarModule, InrPipe, TranslatePipe, CountUpDirective, ChatBarComponent, CoverageEstimateComponent],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
})
export class HomeComponent {
  private api = inject(ApiService);
  private router = inject(Router);
  private chat = inject(ChatService);
  policy = toSignal(this.api.getPolicy());
  claimCase = toSignal(this.api.getCase());
  settlement = toSignal(this.api.getSettlement());
  bill = toSignal(this.api.getBill());
  readonly live = isLive('policy') && isLive('upload');
  demoLoading = signal(false);
  demoError = signal<string | null>(null);

  readonly greeting = (() => {
    const h = new Date().getHours();
    return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  })();

  firstName = computed(() => {
    const members = this.policy()?.members ?? [];
    const self = members.find((m) => /self|proposer|insured/i.test(m.relation)) ?? members[0];
    return self?.name.split(' ')[0] ?? 'there';
  });

  totalDeducted = computed(() => this.settlement()?.deductions.reduce((sum, d) => sum + d.amount, 0) ?? 0);
  approvedPct = computed(() => {
    const s = this.settlement();
    return s && s.claimedAmount ? Math.round((s.approvedAmount / s.claimedAmount) * 100) : 0;
  });

  claimItems = computed(() => (this.claimCase()?.checklist ?? []).filter((i) => i.group === 'claim'));

  waits = computed<WaitRow[]>(() => {
    const now = Date.now();
    return (this.policy()?.waitingPeriods ?? [])
      .filter((w) => w.startDate && w.endDate)
      .map((w) => {
        const start = Date.parse(w.startDate);
        const end = Date.parse(w.endDate);
        const over = end <= now;
        return {
          id: w.id, label: w.label, endDate: w.endDate, over,
          pct: over ? 100 : Math.max(0, Math.min(100, Math.round(((now - start) / Math.max(end - start, 1)) * 100))),
          left: over ? 'Over' : timeLeft(Math.ceil((end - now) / DAY)),
        };
      });
  });
  nextWait = computed(() => this.waits().filter((w) => !w.over).sort((a, b) => a.endDate.localeCompare(b.endDate))[0]);

  attention = computed<Attention[]>(() => {
    const items: Attention[] = [];
    if (this.bill()?.reviewed === false) {
      items.push({ tone: 'warn', icon: 'fact_check', title: 'Check the details we read from your bill',
        text: 'Compare them with your paper bill before you rely on the checks or write to the insurer.', route: '/case/bill', fragment: 'review' });
    }
    // The next step itself is in the banner (strip and big button), so this list holds the other things to do.
    const next = this.journey.nextAction();
    const s = this.settlement();
    const unknown = (s?.deductions ?? []).filter((d) => d.trust === 'unknown');
    if (unknown.length && !this.journey.lastSent() && !next?.title.includes('no clear reason')) {
      const amount = unknown.reduce((sum, d) => sum + d.amount, 0);
      items.push({ tone: 'bad', icon: 'help_outline', title: `${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount)} cut with no clear reason`,
        text: 'Ask the insurer to explain. We can write the letter for you.', route: '/case/settlement', fragment: unknown[0].id });
    }
    const missing = this.claimItems().filter((i) => i.status === 'missing');
    if (missing.length) {
      items.push({ tone: 'warn', icon: 'assignment_late', title: `Collect ${missing.length} more paper${missing.length === 1 ? '' : 's'} for your claim`,
        text: missing.slice(0, 3).map((i) => i.name).join(', ') + (missing.length > 3 ? '…' : ''), route: '/case', fragment: 'checklist' });
    }
    for (const c of (this.bill()?.checks ?? []).filter((c) => c.severity === 'high').slice(0, 1)) {
      items.push({ tone: 'warn', icon: 'receipt_long', title: 'Ask the hospital about your bill', text: c.message, route: '/case/bill', fragment: 'checks' });
    }
    for (const f of (this.policy()?.flags ?? []).slice(0, 1)) {
      items.push({ tone: 'unknown', icon: 'policy', title: 'Check this in your policy', text: f.message, route: '/policy' });
    }
    const unsure = (this.policy()?.traps ?? []).filter((t) => t.trust !== 'supported');
    if (unsure.length) {
      items.push({ tone: 'unknown', icon: 'warning_amber', title: unsure[0].title, text: 'Check this before your next hospital stay.', route: '/policy', fragment: 'traps' });
    }
    return items.slice(0, 4);
  });

  private journey = inject(JourneyService);
  readonly steps = this.journey.steps;
  readonly currentStep = this.journey.currentIndex;
  readonly doneCount = this.journey.doneCount;
  readonly rejection = this.journey.rejection;
  readonly next = this.journey.nextAction;

  /** Claim pages for the summary card and the phone tiles. Policy and Ask are left out: the main navigation already has them. */
  readonly webTabs: Service[] = [
    { icon: 'receipt_long', label: 'Check my bill', route: '/case/bill' },
    { icon: 'stacked_bar_chart', label: 'Why money was cut', route: '/case/settlement' },
    { icon: 'edit_note', label: 'Write to the insurer', route: '/case/letter' },
    { icon: 'mark_email_read', label: "Insurer's reply", route: '/case/reply' },
    { icon: 'quiz', label: "Insurer's question", route: '/case/query' },
    { icon: 'checklist', label: 'Papers checklist', route: '/case', fragment: 'checklist' },
    { icon: 'history_edu', label: 'Claim diary', route: '/case', fragment: 'diary' },
    { icon: 'upload_file', label: 'Add documents', route: '/upload' },
  ];
  readonly bigTiles = this.webTabs.slice(0, 4);
  readonly smallTiles = this.webTabs.slice(4);

  /** The service tab that matches the next thing to do gets the underline. */
  isNext(s: Service): boolean {
    const n = this.next();
    return !!n && n.route === s.route && (!s.fragment || s.fragment === n.fragment);
  }

  readonly heroTitle = computed(() => {
    const c = this.claimCase();
    if (c && (this.settlement() || this.rejection() || this.bill())) return c.title;
    return this.policy() ? 'Your cover at a glance' : 'Your health insurance, in plain words';
  });

  readonly fields = computed<HeroField[]>(() => {
    const c = this.claimCase();
    const s = this.settlement();
    const r = this.rejection();
    const b = this.bill();
    const p = this.policy();
    if (c && (s || r || b)) {
      const stay = c.admissionDate ? `${shortDate(c.admissionDate)} – ${shortDate(c.dischargeDate)}` : '—';
      const money: HeroField[] = s
        ? [
          { label: 'Claimed', value: formatInr(s.claimedAmount), amount: s.claimedAmount, sub: 'What you asked for', route: '/case/bill' },
          { label: 'Insurer paid', value: formatInr(s.approvedAmount), amount: s.approvedAmount, donut: this.approvedPct(), sub: `${this.approvedPct()}% of the claim`, tone: 'ok', route: '/case/settlement' },
          { label: 'Cut', value: formatInr(this.totalDeducted()), amount: this.totalDeducted(), sub: 'Tap to see why', tone: 'bad', route: '/case/settlement' },
        ]
        : r
          ? [{ label: 'Decision', value: 'Refused', sub: r.reason || 'See their reason', tone: 'bad', wide: true, route: '/case/settlement' }]
          : [{ label: 'Bill total', value: formatInr(b!.total), sub: 'Waiting for the insurer', wide: true, route: '/case/bill' }];
      return [
        { label: 'Patient', value: c.patient.name, sub: [c.patient.relation, c.hospital].filter(Boolean).join(' · '), wide: true, route: '/case' },
        { label: 'Hospital stay', value: stay, sub: c.diagnosis, route: '/case' },
        ...money,
      ];
    }
    if (p) {
      return [
        { label: 'Plan', value: p.planName, sub: p.insurer, wide: true, route: '/policy' },
        { label: 'Total cover', value: p.sumInsured ? formatInr(p.sumInsured) : 'Add it', sub: p.policyType, route: '/policy', fragment: 'details' },
        { label: 'Room limit', value: p.roomRent.amount ? `${formatInr(p.roomRent.amount)}/day` : 'Add it', sub: 'Pick a room within this', route: '/policy', fragment: 'room-rent' },
        { label: 'People covered', value: String(p.members.length), sub: this.memberNames(), route: '/policy', fragment: 'details' },
      ];
    }
    return [];
  });

  /** The big button under the summary card. */
  readonly cta = computed(() => {
    const n = this.next();
    return n ? { label: n.action, route: n.route, fragment: n.fragment, query: n.query } : { label: 'Add documents', route: '/upload', fragment: undefined, query: undefined };
  });

  /** Data still on its way: the summary card shows grey placeholders of the same shape. */
  readonly loading = computed(() => this.claimCase() === undefined || this.policy() === undefined);

  /** Latest claim-diary entries, newest first, for the strip on the dashboard. */
  readonly recentDiary = computed(() => [...this.journey.timeline()].reverse().slice(0, 6));
  diaryText(e: TimelineEvent): string {
    return eventText(e);
  }
  /** Circumference of the paid ring (r = 15). */
  readonly ring = 2 * Math.PI * 15;

  readonly tips: Tip[] = [
    { icon: 'bed', title: 'Room-rent tip', text: 'Pick a room within your daily limit. A costlier room can shrink every other charge too.', action: 'See my limit', route: '/policy', fragment: 'room-rent' },
    { icon: 'event_available', title: "Before you're admitted", text: 'Ask the hospital for a cost estimate, and check your waiting times.', action: 'Waiting times', route: '/policy', fragment: 'waiting-periods' },
    { icon: 'checklist', title: 'Papers checklist', text: 'Keep the final bill, discharge summary, test reports and every receipt.' },
    { icon: 'local_hospital', title: 'Cashless or pay first?', text: 'Cashless needs approval before treatment. If you pay first, claim within the time limit.', action: 'Ask how', ask: 'How do I file my claim?' },
    { icon: 'receipt_long', title: 'Ask for a detailed bill', text: 'A bill with every charge listed makes each cut easier to question.' },
    { icon: 'schedule', title: 'Note every date', text: 'Write down when you send papers and letters. You need the dates if you complain.' },
  ];

  scrollTips(row: HTMLElement, direction: 1 | -1): void {
    row.scrollBy({ left: direction * Math.max(260, row.clientWidth * 0.8), behavior: 'smooth' });
  }

  readonly tab = signal<'waits' | 'people'>('waits');
  readonly tabs = computed(() => [
    ...(this.waits().length ? [{ id: 'waits' as const, label: 'Waiting times', short: 'Waits', icon: 'hourglass_bottom' }] : []),
    ...(this.policy()?.members?.length ? [{ id: 'people' as const, label: 'People covered', short: 'People', icon: 'groups' }] : []),
  ]);
  /** The chosen tab, or the first one shown when the chosen one isn't available. */
  readonly activeTab = computed(() => (this.tabs().some((t) => t.id === this.tab()) ? this.tab() : this.tabs()[0]?.id));

  /** Arrow keys move between tabs (standard tab pattern). */
  onTabKey(e: KeyboardEvent): void {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const ids = this.tabs().map((t) => t.id);
    const i = ids.indexOf(this.activeTab()!);
    const next = ids[(i + (e.key === 'ArrowRight' ? 1 : ids.length - 1)) % ids.length];
    this.tab.set(next);
    setTimeout(() => document.getElementById('tab-' + next)?.focus());
  }

  readonly showWelcome = signal(!localStorage.getItem('carenest.onboarded'));
  dismissWelcome(): void {
    this.showWelcome.set(false);
    try { localStorage.setItem('carenest.onboarded', '1'); } catch { /* private mode */ }
  }

  loadDemo(): void {
    this.demoLoading.set(true);
    this.demoError.set(null);
    this.api.loadDemoCase().subscribe({
      next: () => this.router.navigate(['/case/settlement']),
      error: (e) => {
        this.demoLoading.set(false);
        this.demoError.set(e?.error?.detail ?? 'Loading the demo case failed. Please try again.');
      },
    });
  }

  memberNames(): string {
    return this.policy()?.members.map((m) => m.name.split(' ')[0]).join(', ') ?? '';
  }

  initials(name: string): string {
    return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
  }

  ask(question: string): void {
    if (question) this.chat.ask(question);
    else this.chat.openPanel();
  }
}
