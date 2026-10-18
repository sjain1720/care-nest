/** Pages for working on a claim: listed in the menu under Claim tools, and used for the breadcrumb on those pages. */
export interface ClaimTool {
  path: string;
  label: string;
  icon: string;
  desc: string;
}

export const CLAIM_TOOLS: ClaimTool[] = [
  { path: '/bills', label: 'Hospital bills', icon: 'receipt_long', desc: 'Original files and the current bill check' },
  { path: '/case/query', label: "Insurer's question", icon: 'quiz', desc: 'They asked for more during your stay' },
  { path: '/case/bill', label: 'Check my bill', icon: 'receipt_long', desc: 'Charges that may not be paid' },
  { path: '/case/settlement', label: 'Why money was cut', icon: 'stacked_bar_chart', desc: 'Each cut, in plain words' },
  { path: '/case/letter', label: 'Write to the insurer', icon: 'edit_note', desc: 'Letters, ready to send' },
  { path: '/case/reply', label: "Insurer's reply", icon: 'mark_email_read', desc: 'What their answer means' },
  { path: '/upload', label: 'Add documents', icon: 'upload_file', desc: 'Policy, bill, letters' },
];
