import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { InrPipe } from '../../shared/inr.pipe';

interface Journey {
  icon: string;
  title: string;
  text: string;
  route: string;
  query?: Record<string, string>;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule, InrPipe],
  templateUrl: './home.component.html',
  styles: `
    .hero { background: linear-gradient(120deg, #005cbb, #0a7f8a); color: #fff; border: 0; }
    .hero h1 { color: #fff; }
    .hero p { margin: 0 0 12px; opacity: .95; }
    .hero .amount { font-size: 1.6rem; }
    .hero-btn { background: #fff !important; color: #005cbb !important; }
    .journey { display: flex; flex-direction: column; gap: 6px; text-decoration: none; color: inherit; min-height: 150px;
               transition: border-color .15s, transform .15s; }
    .journey:hover { border-color: var(--cn-primary); transform: translateY(-2px); }
    .journey mat-icon { color: var(--cn-primary); font-size: 32px; width: 32px; height: 32px; }
    .journey p { margin: 0; color: var(--cn-muted); font-size: .9rem; }
    .quick { display: flex; flex-wrap: wrap; gap: 8px; }
    .quick a { text-decoration: none; }
  `,
})
export class HomeComponent {
  private api = inject(ApiService);
  policy = toSignal(this.api.getPolicy());
  claimCase = toSignal(this.api.getCase());
  settlement = toSignal(this.api.getSettlement());

  readonly journeys: Journey[] = [
    { icon: 'event_note', title: 'Planning a treatment', text: 'Check if it is covered, the waiting periods and the room limit before admission.', route: '/ask', query: { q: "Is my father's cataract surgery covered?" } },
    { icon: 'local_hospital', title: 'In hospital now', text: 'Understand insurer queries, check the running bill and know which papers to collect.', route: '/case' },
    { icon: 'assignment_turned_in', title: 'Discharged, filing a claim', text: 'Get your personal document checklist and a cover letter.', route: '/case' },
    { icon: 'report_problem', title: 'Claim cut or rejected', text: 'See every deduction explained against your policy, and draft a reply.', route: '/case/settlement' },
  ];

  readonly quickQuestions = [
    "Is my father's cataract surgery covered?",
    'What is my room-rent limit?',
    'Why was ₹38,000 deducted from my mother’s claim?',
    'Is diabetes treatment covered?',
  ];

  totalDeducted(): number {
    return this.settlement()?.deductions.reduce((sum, d) => sum + d.amount, 0) ?? 0;
  }

  memberNames(): string {
    return this.policy()?.members.map((m) => m.name.split(' ')[0]).join(', ') ?? '';
  }
}
