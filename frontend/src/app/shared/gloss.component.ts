import { Component, computed, input } from '@angular/core';
import { MatTooltipModule } from '@angular/material/tooltip';
import { TranslatePipe } from './translate.pipe';

/** One-line meanings for insurance words. Keys are lower case, without hyphens or plurals. */
const GLOSSARY: Record<string, string> = {
  'copay': 'The share of the bill you pay yourself, even when the claim is approved.',
  'waiting period': 'Time after the policy starts before an illness or treatment is covered.',
  'waiting time': 'Time after the policy starts before an illness or treatment is covered.',
  'sublimit': 'The most the insurer pays for one treatment or item, even if your total cover is higher.',
  'deductible': 'An amount you pay first, before the insurer starts paying.',
  'tpa': 'Third Party Administrator: the company that handles claims for the insurer.',
  'cashless': 'The insurer pays the hospital directly, so you pay only what is not covered.',
  'reimbursement': 'You pay the hospital first, then claim the money back from the insurer.',
  'preexisting disease': 'An illness you had before you bought the policy. It is covered only after a waiting period.',
  'preauthorisation': "The insurer's approval, before or during a hospital stay, to pay the hospital directly.",
  'preauthorization': "The insurer's approval, before or during a hospital stay, to pay the hospital directly.",
  'preauth': "The insurer's approval, before or during a hospital stay, to pay the hospital directly.",
  'room rent': 'What the hospital charges per day for your room. Your policy may limit it.',
  'sum insured': 'The most the insurer pays in a policy year. Also called total cover.',
  'nonpayable': 'Items the insurer never pays for, such as gloves and admission kits.',
  'consumable': 'Single-use items like gloves, masks and kits. Usually not paid unless you have extra cover.',
  'settlement letter': 'The insurer\u2019s letter saying how much it paid and what it cut.',
  'proportionate deduction': 'If your room costs more than your limit, the insurer cuts other charges by the same share.',
  'discharge summary': 'The hospital\u2019s note on your illness and treatment, given when you leave.',
  'daycare': 'Treatment that needs less than 24 hours in hospital, like cataract surgery.',
  'network hospital': 'A hospital that has a cashless agreement with your insurer.',
  'portability': 'Moving your policy to another insurer without losing the waiting time already served.',
  'ombudsman': 'A free, independent official who settles complaints against insurers.',
  'grievance': 'A formal complaint to the insurer.',
  'irdai': 'The Insurance Regulatory and Development Authority of India, which oversees insurers.',
  'kyc': 'Know Your Customer: proof of who you are, like PAN or Aadhaar.',
  'annexure': 'An extra list at the end of the policy, for example of items not paid.',
};

const PATTERN = new RegExp(
  '\\b(co-?pay|waiting periods?|waiting times?|sub-?limits?|deductibles?|TPA|cashless|reimbursement|pre-?existing diseases?|' +
  'pre-?authori[sz]ation|pre-?auth|room[- ]rent|sum insured|non-?payable|consumables?|settlement letters?|proportionate deductions?|' +
  'discharge summary|day-?care|network hospitals?|portability|ombudsman|grievances?|IRDAI|KYC|annexures?)\\b',
  'gi',
);

function definition(term: string): string | undefined {
  const key = term.toLowerCase().replace(/^room-rent$/, 'room rent').replace(/-/g, '');
  return GLOSSARY[key] ?? GLOSSARY[key.replace(/s$/, '')];
}

interface Part {
  text: string;
  def?: string;
}

/** Text where insurance words have a dotted underline; tap or hover shows what they mean. */
@Component({
  selector: 'app-gloss',
  standalone: true,
  imports: [MatTooltipModule, TranslatePipe],
  template: `@for (p of parts(); track $index) {@if (p.def) {<button type="button" class="term" [matTooltip]="p.def | t" matTooltipClass="cn-term-tip" #tip="matTooltip" (click)="tip.toggle()" [attr.aria-label]="p.text + ': ' + (p.def | t)">{{ p.text }}</button>} @else {<span>{{ p.text }}</span>}}`,
  styles: `
    .term { display: inline; padding: 0; margin: 0; border: 0; background: none; font: inherit; color: inherit; cursor: help;
            text-decoration: underline dotted var(--cn-green-strong); text-underline-offset: 3px; text-decoration-thickness: 2px; }
    .term:focus-visible { outline: 2px solid var(--cn-focus); border-radius: 3px; }
  `,
})
export class GlossComponent {
  text = input<string | null | undefined>('');

  readonly parts = computed<Part[]>(() => {
    const text = this.text() ?? '';
    const parts: Part[] = [];
    const seen = new Set<string>();
    let last = 0;
    for (const m of text.matchAll(PATTERN)) {
      const def = definition(m[0]);
      const key = m[0].toLowerCase();
      if (!def || seen.has(key)) continue;
      seen.add(key);
      if (m.index! > last) parts.push({ text: text.slice(last, m.index) });
      parts.push({ text: m[0], def });
      last = m.index! + m[0].length;
    }
    if (last < text.length) parts.push({ text: text.slice(last) });
    return parts;
  });
}
