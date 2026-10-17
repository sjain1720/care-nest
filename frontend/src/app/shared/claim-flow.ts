import { Bill, ClaimCase, LetterKind } from '../models/models';

export interface FlowLink { label: string; route: string; query?: Record<string,string>; fragment?: string; }
export interface FlowState { stage: number; next: FlowLink; note: string; }
export const FLOW_STAGES = ['Documents', 'Review & prepare response', 'Insurer reply', 'Outcome'];

/** Page grouping is navigation, not a record of external sending/payment/closure. */
export function resolveClaimFlow(c: ClaimCase | null | undefined, bill: Bill | null | undefined,
  decided: boolean, path: string, section: string | null, outcome: boolean, kind: string | null): FlowState {
  const events = [...(c?.timeline ?? [])].sort((a,b) => a.date.localeCompare(b.date));
  const reply = events.filter(e => e.kind === 'reply').at(-1);
  const closed = events.at(-1)?.kind === 'closed';
  const needsPapers = reply?.outcome === 'asks_for_papers';
  const letter: LetterKind = needsPapers ? 'document_response' : c?.rejection ? 'reconsideration' : decided ? 'clarification' : 'cover_letter';
  const draft: FlowLink = {label: needsPapers ? 'Prepare response with current documents' : 'Prepare letter with current documents',route:'/case/letter',query:{kind:letter}};
  const documents: FlowLink = {label:'Review requested documents',route:'/case',query:{section:'documents'}};
  const stage = outcome ? 3 : path === '/case/reply' ? 2 : path === '/upload' || (path === '/case' && section === 'documents') ? 0 : 1;
  if (closed) return {stage:3,next:{label:'Review claim history',route:'/case',query:{section:'history'}},note:'Closed by you. Use the claim diary to reopen if needed.'};
  if (path === '/case/reply') {
    if (needsPapers) return {stage,next:documents,note:'Upload and review the requested items, then prepare a response. Uploading does not send them.'};
    if (!reply) return {stage,next:{label:'Add the insurer reply',route:'/case/reply',fragment:'add'},note:'Paste or upload an existing reply. Do not record sending unless you actually sent a letter.'};
    return {stage,next:{label:'Review outcome and next action',route:'/case',query:{section:'history',outcome:'1'}},note:'Approval is not payment. Closing a claim is your decision.'};
  }
  if (outcome && reply) return {stage,next: reply.outcome === 'asks_for_papers' ? documents : {label:'Prepare a follow-up',route:'/case/letter',query:{kind:reply.outcome === 'no_change' || reply.outcome === 'rejected' ? 'grievance' : letter}},note:'Review the reply and your options. No automatic closure or refund is claimed.'};
  if (path === '/case/letter') {
    const sent = events.some(e => (e.kind === 'letter_sent' && e.letterKind === kind && (!needsPapers || e.replyId === reply?.id)) || (kind === 'cover_letter' && e.kind === 'claim_sent') || (kind === 'grievance' && e.kind === 'complaint_filed'));
    return {stage,next:sent ? {label:'Add the insurer reply',route:'/case/reply'} : {label:'Record when you sent it',route:'/case/letter',query:{kind:kind ?? letter},fragment:'sent'},note:'Review, download and send through your insurer’s channel yourself. Downloading is not sending.'};
  }
  if (needsPapers) return {stage,next:draft,note:'You can prepare a partial response. Missing or unchecked requested items remain listed.'};
  if (path === '/case/settlement') return {stage,next:draft,note:'Keep any unresolved policy or calculation questions in your response.'};
  if (bill && !bill.reviewed) return {stage,next:{label:'Review the bill reading',route:'/case/bill',fragment:'review'},note:'Check extracted rows before relying on analysis. Missing papers do not prevent drafting a letter.'};
  return {stage,next:decided ? {label:'Review the insurer decision',route:'/case/settlement'} : draft,note:'Continue with the documents you have. The checklist is guidance; confirm actual insurer requirements.'};
}
