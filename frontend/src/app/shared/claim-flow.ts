import { Bill, ClaimCase, LetterKind } from '../models/models';

export interface FlowLink { label: string; route: string; query?: Record<string,string>; fragment?: string; }
export type StepId = 'policy'|'bill'|'documents'|'submit'|'decision'|'response'|'send'|'reply'|'outcome';
export type StepStatus = 'Done'|'Current'|'Waiting'|'Needs review'|'Not needed';
export interface JourneyStep extends FlowLink { id: StepId; status: StepStatus; done: boolean; todo: string; }
export interface ClaimJourney { steps: JourneyStep[]; currentIndex: number; note: string; }
export const STEP_LABELS = ['Add policy','Review bill','Prepare documents','Submit claim','Add insurer decision','Review decision & prepare response','Send follow-up','Review insurer reply','Record outcome'];
const IDS: StepId[] = ['policy','bill','documents','submit','decision','response','send','reply','outcome'];

/** Derives navigation from recorded facts. Selecting a page never records sending or closure. */
export function claimJourney(c: ClaimCase | null | undefined, bill: Bill | null | undefined,
  hasPolicy: boolean, decided: boolean, noDeductions: boolean, reviewedResponse = false, requestedReady = false): ClaimJourney {
  const events = [...(c?.timeline ?? [])].sort((a,b) => a.date.localeCompare(b.date));
  const reply = events.filter(e => e.kind === 'reply').at(-1);
  const sent = events.filter(e => e.kind === 'letter_sent' || e.kind === 'complaint_filed').at(-1);
  const closed = events.filter(e => e.kind !== 'outcome_recorded').at(-1)?.kind === 'closed';
  const claimSent = events.some(e => e.kind === 'claim_sent') || decided;
  const needsPapers = reply?.outcome === 'asks_for_papers';
  // A response to another request cannot complete this request's sending step.
  const responseSent = !!sent && (!needsPapers || sent.replyId === reply?.id) && (!reply || events.indexOf(sent) > events.indexOf(reply));
  const answered = !!reply && (!sent || events.indexOf(reply) > events.indexOf(sent));
  const optional = noDeductions && !sent && !reply;
  const papers = (c?.checklist ?? []).filter(i => i.group === 'claim');
  const papersReady = papers.length > 0 && papers.every(i => i.status === 'collected');
  const letter: LetterKind = needsPapers ? 'document_response' : c?.rejection ? 'reconsideration' : 'clarification';
  let current = !hasPolicy ? 0 : !bill?.reviewed ? 1 : decided ? optional ? 8 : responseSent ? 7 : answered && !needsPapers ? 8 : reviewedResponse ? 6 : needsPapers && !requestedReady ? 2 : 5 : claimSent ? 4 : papersReady ? 3 : 2;
  if (closed) current = 8;
  const completed = [hasPolicy, bill?.reviewed === true, needsPapers ? requestedReady : papersReady, claimSent, decided,
    reviewedResponse || (needsPapers ? responseSent : !!sent), needsPapers ? responseSent : !!sent, answered, closed];
  const links: FlowLink[] = [
    {label:STEP_LABELS[0],route:'/policy',query:{step:'policy'}},
    {label:STEP_LABELS[1],route:'/case/bill'},
    {label:STEP_LABELS[2],route:'/case/detail',query:{step:'documents'}},
    {label:STEP_LABELS[3],route:'/case/letter',query:{step:'submit',kind:'cover_letter'}},
    {label:STEP_LABELS[4],route:'/case/settlement',query:{step:'decision'}},
    {label:STEP_LABELS[5],route:'/case/settlement',query:{step:'response'}},
    {label:STEP_LABELS[6],route:'/case/letter',query:{step:'send',kind:letter},fragment:'sent'},
    {label:STEP_LABELS[7],route:'/case/reply'},
    {label:STEP_LABELS[8],route:'/case/detail',query:{step:'outcome'}},
  ];
  const steps = links.map((link,i): JourneyStep => {
    let status: StepStatus = completed[i] ? 'Done' : 'Needs review';
    if (i >= 5 && i <= 7 && optional) status = 'Not needed';
    if (i >= 5 && i <= 7 && closed && !completed[i]) status = 'Not needed';
    if (i === current && !closed) status = (i === 4 && claimSent && !decided) || (i === 7 && responseSent) ? 'Waiting' : 'Current';
    return {...link,id:IDS[i],status,done:status === 'Done',todo:link.label};
  });
  const note = closed ? 'Closed by you. Your documents and correspondence remain available below.'
    : decided && !bill?.reviewed ? 'The insurer’s decision is already available. Review the bill before examining the deductions; your submission history is preserved.'
    : needsPapers && !responseSent ? 'The insurer requested more documents. Review those tasks, then prepare a response. You may draft while some items are missing.'
    : optional ? 'No deductions are recorded. Confirm payment or another outcome before choosing whether to close the claim.'
    : current === 7 ? 'Waiting for a reply. Add it when it arrives; sending a follow-up does not close the claim.'
    : current === 4 ? 'Your original submission is recorded. Add the insurer’s decision when it arrives.'
    : 'Continue with the documents you have. Sending and closing are actions you record yourself.';
  return {steps,currentIndex:closed ? -1 : current,note};
}

export function selectedClaimStep(path: string, step: string | null, section: string | null, fragment: string | null, kind: string | null, current: number): number {
  if (step && IDS.includes(step as StepId)) return IDS.indexOf(step as StepId);
  if (path === '/policy') return 0;
  if (path === '/case/bill') return 1;
  if (path === '/case/reply') return 7;
  if (path === '/case/letter') return kind === 'cover_letter' ? 3 : fragment === 'sent' ? 6 : 5;
  if (path === '/case/settlement') return 5;
  if (section === 'documents' || ['checklist','documents','dispute-papers'].includes(fragment ?? '')) return 2;
  if (section === 'history' || fragment === 'diary') return 8;
  return current < 0 ? 8 : current;
}
