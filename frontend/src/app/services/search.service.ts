import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { combineLatest } from 'rxjs';
import { ApiService } from './api.service';
import { ChatService } from './chat.service';
import { Bill, ClaimCase, PolicyFacts, Settlement } from '../models/models';
import { scrollToSection } from '../shared/scroll';

export type SearchGroup = 'Go to' | 'In your policy' | 'In your claim' | 'Ask CareNest';

export interface SearchItem {
  group: SearchGroup;
  icon: string;
  label: string;
  hint?: string;
  keywords?: string;
  route?: string;
  fragment?: string;
  ask?: string;
}

const GROUP_ORDER: SearchGroup[] = ['Ask CareNest', 'Go to', 'In your policy', 'In your claim'];
const GROUP_LIMIT: Record<SearchGroup, number> = { 'Ask CareNest': 3, 'Go to': 4, 'In your policy': 3, 'In your claim': 3 };
const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const DATE = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

const PAGES: SearchItem[] = [
  { group: 'Go to', icon: 'dashboard', label: 'Home', route: '/', keywords: 'home overview summary start' },
  { group: 'Go to', icon: 'policy', label: 'My policy', route: '/policy', keywords: 'cover coverage plan insurance sum insured' },
  { group: 'Go to', icon: 'badge', label: 'Policy details and people covered', route: '/policy', fragment: 'details', keywords: 'start date renewal family members deductible edit correct schedule' },
  { group: 'Go to', icon: 'rule', label: 'Limits on what the insurer pays', route: '/policy', fragment: 'limits', keywords: 'copay co-pay sub-limit cap maximum limits' },
  { group: 'Go to', icon: 'bed', label: 'Check room cost', route: '/policy', fragment: 'room-rent', keywords: 'room rent icu single private ward category simulator admission' },
  { group: 'Go to', icon: 'warning_amber', label: 'Watch out for these (policy traps)', route: '/policy', fragment: 'traps', keywords: 'traps exclusions not paid hidden fine print' },
  { group: 'Go to', icon: 'hourglass_bottom', label: 'Waiting times before cover starts', route: '/policy', fragment: 'waiting-periods', keywords: 'waiting period pre-existing ped when covered' },
  { group: 'Go to', icon: 'folder_shared', label: 'My claim', route: '/case', keywords: 'case claim hospital admission status' },
  { group: 'Go to', icon: 'checklist', label: 'Papers checklist', route: '/case', fragment: 'checklist', keywords: 'documents missing claim form receipts kyc file claim checklist' },
  { group: 'Go to', icon: 'gavel', label: 'Extra papers to question a cut', route: '/case', fragment: 'dispute-papers', keywords: 'dispute challenge appeal deduction' },
  { group: 'Go to', icon: 'picture_as_pdf', label: 'Your uploaded files', route: '/case', fragment: 'documents', keywords: 'files pdf uploaded documents' },
  { group: 'Go to', icon: 'receipt_long', label: 'Check my bill', route: '/case/bill', keywords: 'hospital bill charges invoice' },
  { group: 'Go to', icon: 'savings', label: 'What you may pay yourself', route: '/case/bill', fragment: 'estimate', keywords: 'estimate out of pocket non-payable not paid' },
  { group: 'Go to', icon: 'list_alt', label: 'Every charge on the bill', route: '/case/bill', fragment: 'charges', keywords: 'items line items consumables medicines' },
  { group: 'Go to', icon: 'stacked_bar_chart', label: 'Why money was cut', route: '/case/settlement', keywords: 'settlement deduction deducted cut approved paid less waterfall' },
  { group: 'Go to', icon: 'edit_note', label: 'Write to the insurer', route: '/case/letter', keywords: 'letter email reply grievance complaint reconsideration draft' },
  { group: 'Go to', icon: 'quiz', label: 'The insurer asked a question', route: '/case/query', keywords: 'tpa query pre-auth preauthorisation cashless hospital desk' },
  { group: 'Go to', icon: 'upload_file', label: 'Add documents', route: '/upload', keywords: 'upload add pdf scan file' },
  { group: 'Go to', icon: 'forum', label: 'Ask CareNest (full page)', route: '/ask', keywords: 'chat question assistant ai help' },
  { group: 'Go to', icon: 'tune', label: 'Demo and live settings', route: '/status', keywords: 'live demo settings status backend' },
];

const QUESTIONS = [
  "Is my father's cataract surgery covered?",
  'What is my room-rent limit?',
  'Why was money deducted from my claim?',
  'Which documents am I missing?',
  'How much will I have to pay from this bill?',
  'Is diabetes treatment covered?',
  'Which waiting periods are still running?',
  'The TPA sent a query on my pre-auth, what do I do?',
  'How do I file my claim?',
  'Can I challenge a deduction?',
].map<SearchItem>((q) => ({ group: 'Ask CareNest', icon: 'auto_awesome', label: q, ask: q }));

const SUGGESTED: SearchItem[] = [PAGES[14], PAGES[8], PAGES[6], PAGES[12], QUESTIONS[2], QUESTIONS[0]];

const norm = (s: string) => s.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9₹ ]+/g, ' ');

/** Finds pages, sections, policy facts, claim items and questions for the header search. */
@Injectable({ providedIn: 'root' })
export class SearchService {
  private api = inject(ApiService);
  private chat = inject(ChatService);
  private router = inject(Router);
  private dataItems = signal<SearchItem[]>([]);

  /** Re-reads the cached policy and case data (call when the search box gets focus). */
  refresh(): void {
    combineLatest([this.api.getPolicy(), this.api.getCase(), this.api.getSettlement(), this.api.getBill()]).subscribe(
      ([p, c, s, b]) => this.dataItems.set([...policyItems(p), ...caseItems(c, s, b)]),
    );
  }

  /** Grouped suggestions. With an empty query: questions for this page, then popular places. */
  search(query: string, prompts: string[] = []): { group: SearchGroup; items: SearchItem[] }[] {
    const q = norm(query).trim();
    if (!q) {
      const asks = prompts.map<SearchItem>((p) => ({ group: 'Ask CareNest', icon: 'auto_awesome', label: p, ask: p }));
      return group([...asks, ...SUGGESTED.filter((s) => !s.ask)]);
    }

    const tokens = q.split(/\s+/);
    const scored = [...PAGES, ...this.dataItems(), ...QUESTIONS]
      .map((item) => ({ item, score: score(item, q, tokens) }))
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((r) => r.item);

    const free: SearchItem = { group: 'Ask CareNest', icon: 'send', label: `Ask: "${query.trim()}"`, ask: query.trim() };
    return group([free, ...scored]);
  }

  open(item: SearchItem): void {
    if (item.ask) {
      this.chat.ask(item.ask);
      return;
    }
    this.router.navigate([item.route ?? '/'], { fragment: item.fragment }).then(() => {
      if (item.fragment) scrollToSection(item.fragment);
      else scrollTo({ top: 0 });
    });
  }
}

function score(item: SearchItem, q: string, tokens: string[]): number {
  const label = norm(item.label);
  const text = `${label} ${norm(item.hint ?? '')} ${norm(item.keywords ?? '')}`;
  if (!tokens.every((t) => text.includes(t))) return 0;
  let s = 1;
  if (label.startsWith(q)) s += 4;
  else if (label.includes(q)) s += 2;
  s += tokens.filter((t) => new RegExp(`(^|\\s)${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`).test(label)).length;
  if (item.group === 'Ask CareNest') s -= 1;
  return s;
}

function group(items: SearchItem[]): { group: SearchGroup; items: SearchItem[] }[] {
  return GROUP_ORDER.map((g) => {
    const inGroup = items.filter((i) => i.group === g);
    // The typed "Ask: …" option always comes first, so Enter asks the assistant.
    const free = inGroup.find((i) => i.icon === 'send');
    const rest = inGroup.filter((i) => i !== free && i.label !== free?.ask).slice(0, GROUP_LIMIT[g] - (free ? 1 : 0));
    return { group: g, items: free ? [free, ...rest] : rest };
  }).filter((g) => g.items.length);
}

function policyItems(p: PolicyFacts | null): SearchItem[] {
  if (!p) return [];
  const today = new Date().toISOString().slice(0, 10);
  const g: SearchGroup = 'In your policy';
  return [
    { group: g, icon: 'account_balance_wallet', label: `Total cover: ${p.sumInsured ? INR.format(p.sumInsured) : 'not found'}`, route: '/policy', fragment: 'details', keywords: 'sum insured cover amount total limit' },
    { group: g, icon: 'bed', label: `Room rent: ${p.roomRent.label}`, route: '/policy', fragment: 'room-rent', keywords: 'room limit per day' },
    { group: g, icon: 'percent', label: `Co-pay (your share): ${p.coPay.label}`, route: '/policy', fragment: 'limits', keywords: 'copay share' },
    ...p.subLimits.map<SearchItem>((s) => ({ group: g, icon: 'rule', label: `${s.label} limit`, hint: s.amount ? `up to ${INR.format(s.amount)} ${s.unit ?? ''}`.trim() : undefined, route: '/policy', fragment: 'limits', keywords: 'cap sub-limit' })),
    ...p.waitingPeriods.map<SearchItem>((w) => ({
      group: g, icon: 'hourglass_bottom', label: w.label, route: '/policy', fragment: 'waiting-periods', keywords: `waiting ${w.appliesTo} ${w.duration}`,
      hint: w.endDate ? (w.endDate <= today ? `Covered since ${DATE.format(new Date(w.endDate))}` : `Covered from ${DATE.format(new Date(w.endDate))}`) : w.duration,
    })),
    ...p.traps.map<SearchItem>((t) => ({ group: g, icon: 'warning_amber', label: t.title, hint: 'Watch out', route: '/policy', fragment: 'traps', keywords: t.explanation })),
    ...p.members.map<SearchItem>((m) => ({ group: g, icon: 'person', label: m.name, hint: `${m.relation}, covered`, route: '/policy', fragment: 'details', keywords: 'family member' })),
  ];
}

function caseItems(c: ClaimCase | null, s: Settlement | null, b: Bill | null): SearchItem[] {
  const g: SearchGroup = 'In your claim';
  const statusLabel = { collected: 'Have it', missing: 'Still needed', requested: 'Asked for' } as const;
  return [
    ...(s?.deductions ?? []).map<SearchItem>((d) => ({ group: g, icon: 'remove_circle_outline', label: d.label, hint: `${INR.format(d.amount)} cut`, route: '/case/settlement', fragment: d.id, keywords: `deduction deducted cut ${d.insurerReason}` })),
    ...(c?.checklist ?? []).map<SearchItem>((i) => ({ group: g, icon: i.status === 'collected' ? 'task_alt' : 'radio_button_unchecked', label: i.name, hint: statusLabel[i.status], route: '/case', fragment: i.group === 'claim' ? 'checklist' : 'dispute-papers', keywords: `document paper ${i.source}` })),
    ...(c?.documents ?? []).map<SearchItem>((d) => ({ group: g, icon: 'picture_as_pdf', label: d.name, hint: d.type, route: '/case', fragment: 'documents', keywords: 'uploaded file' })),
    ...(b?.items ?? []).map<SearchItem>((i) => ({ group: g, icon: 'receipt', label: i.description, hint: `${INR.format(i.amount)} · ${i.category}`, route: '/case/bill', fragment: 'charges', keywords: 'bill charge item' })),
  ];
}
