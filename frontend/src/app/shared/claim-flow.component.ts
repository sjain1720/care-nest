import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { filter, map } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { ApiService } from '../services/api.service';
import { WorkspaceService } from '../services/workspace.service';
import { JourneyService } from '../services/journey.service';
import { FlowLink, selectedClaimStep } from './claim-flow';
import { InrPipe } from './inr.pipe';

@Component({selector:'app-claim-flow',standalone:true,imports:[RouterLink,MatButtonModule,InrPipe],template:`
 @if (visible() && c(); as claim) {
 <div class="journey-shell">
 @if (!footer()) {
 <header class="claim-heading">
   <a class="back-link" routerLink="/case" [queryParams]="{workspace:workspace.mode()}">← All claims</a>
   <h1>{{claim.title || 'Your claim'}}</h1><p>{{claim.patient.name}} · {{claim.hospital || 'Hospital not added yet'}}</p>
   @if(claim.financials;as f){
   <dl class="claim-amounts"><div><dt>Amount claimed</dt><dd>{{f.claimedAmount !== null ? (f.claimedAmount | inr) : 'Not provided'}}</dd></div><div><dt>Insurer approved</dt><dd>{{f.approvedAmount !== null ? (f.approvedAmount | inr) : f.decisionAvailable ? 'Not stated' : 'Awaiting decision'}}</dd></div><div><dt>Payment received</dt><dd>{{f.receivedAmount !== null ? (f.receivedAmount | inr) : 'Not confirmed'}}</dd></div></dl>
   @if(f.billedAmount !== null){<p class="small muted">Hospital bill: {{f.billedAmount | inr}}. Bill total, amount claimed, approval and payment are separate.</p>}
   @if(f.needsReview){<p role="alert">An earlier communication was treated as a decision. Add that insurer response again to correct its classification; the original file is retained.</p>}
   }
 </header>
 <details class="journey no-print" [open]="expanded()" (toggle)="expanded.set($any($event.target).open)">
 <summary><span><strong>Step {{selected()+1}} of 9 · {{steps()[selected()].label}}</strong><small>{{steps()[selected()].status}} · {{journey.doneCount()}} completed</small></span><span class="expand-label">View all steps</span></summary>
 <nav aria-label="Claim journey">@for(step of steps();track step.id;let i=$index){
 <a [routerLink]="step.route" [queryParams]="params(step)" [fragment]="step.fragment" [attr.aria-current]="selected()===i ? 'step' : null" [class.done]="step.done"><span class="number">{{step.done ? '✓' : i+1}}</span><span>{{step.label}}<small>{{step.status}}</small></span></a>
 }</nav>
 </details>
 }
 @if (action(); as next) {
 <aside class="flow-next no-print" [class.card]="footer()" aria-label="Next claim action">
 <div><strong>{{messageTitle()}}</strong><p>{{note()}}</p></div>
 @if (reviewAction()) {<button mat-flat-button (click)="reviewAndContinue()" [disabled]="!journey.draftReady()">I reviewed the draft · Continue →</button>}
 @else {<a mat-flat-button [routerLink]="next.route" [queryParams]="params(next)" [fragment]="next.fragment">{{next.label}} →</a>}
 </aside>
 }
 </div>
 }
`,styles:`
 :host{display:block;min-width:0}.journey-shell{max-width:var(--cn-page-w);box-sizing:border-box;margin:0 auto;padding:12px var(--cn-gutter) 0}.claim-heading h1{margin:8px 0 4px;font-size:clamp(1.3rem,3vw,1.8rem)}.claim-heading p{margin:4px 0 12px;color:var(--cn-muted);font-size:.9rem}
 .claim-amounts{display:flex;flex-wrap:wrap;gap:12px 40px;margin:16px 0 4px}.claim-amounts dt{font-size:.8rem;color:var(--cn-muted)}.claim-amounts dd{margin:2px 0;font-size:1.2rem;font-weight:700;color:var(--cn-strong)}
 .journey{border:1px solid var(--cn-border);border-radius:12px;background:var(--cn-surface);margin:16px 0 12px}.journey summary{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;padding:14px 16px;list-style:none;min-height:48px}.journey summary::-webkit-details-marker{display:none}.journey small{display:block;font-size:.77rem;color:var(--cn-muted);margin-top:4px}.expand-label{font-size:.8rem;color:var(--cn-primary);flex:none}.expand-label:after{content:' ＋'}.journey[open] .expand-label:after{content:' −'}
 nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));padding:0 12px 12px;gap:6px}nav a{display:flex;gap:10px;padding:12px;border-radius:8px;color:var(--cn-ink);text-decoration:none;font-size:.85rem;min-height:56px;align-items:center}nav a:hover{background:var(--cn-bg)}nav a[aria-current]{background:var(--cn-primary-soft);box-shadow:inset 0 0 0 2px var(--cn-primary);font-weight:700}.number{flex:none;display:grid;place-items:center;border:1px solid var(--cn-border-strong);border-radius:50%;width:26px;height:26px}.done .number{background:var(--cn-primary-soft);color:var(--cn-primary)}
 .flow-next{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:12px 0 20px;padding:12px 0}.flow-next.card{padding:16px}.flow-next div{flex:1;min-width:200px}.flow-next p{font-size:.85rem;margin:4px 0;color:var(--cn-muted)}.flow-next a,.flow-next button{white-space:normal;max-width:100%;height:auto;min-height:44px}
 @media(max-width:700px){.journey-shell{padding:12px 12px 0}nav{grid-template-columns:1fr}.journey summary{align-items:flex-start}.expand-label{font-size:.74rem}.flow-next{align-items:flex-start}.claim-amounts{gap:12px 24px}}
`})
export class ClaimFlowComponent {
 readonly expanded=signal(false);
 readonly footer=input(false);readonly workspace=inject(WorkspaceService);readonly journey=inject(JourneyService);
 private api=inject(ApiService);private router=inject(Router);
 private url=toSignal(this.router.events.pipe(filter(e=>e instanceof NavigationEnd),map(()=>this.router.url)),{initialValue:this.router.url});
 constructor(){effect(()=>{this.url();this.expanded.set(false);});}
 readonly path=computed(()=>this.url().split(/[?#]/)[0]);
 private query=computed(()=>this.router.parseUrl(this.url()).queryParams);
 private fragment=computed(()=>this.router.parseUrl(this.url()).fragment);
 readonly c=this.journey.claimCase;readonly settlement=toSignal(this.api.getSettlement());private bill=toSignal(this.api.getBill());private policy=toSignal(this.api.getPolicy());
 readonly visible=computed(()=>this.workspace.mode()!=='general' && (this.path().startsWith('/case/')||this.path()==='/upload'||(this.path()==='/policy'&&this.query()['step']==='policy')||(this.path()==='/case'&&(!!this.query()['section']||['checklist','documents','dispute-papers','diary','overview','next-steps'].includes(this.fragment()??'')))));
 readonly steps=this.journey.steps;
 readonly selected=computed(()=>selectedClaimStep(this.path(),this.query()['step']??null,this.query()['section']??(this.query()['outcome']==='1'?'history':null),this.fragment(),this.query()['kind']??null,this.journey.currentIndex()));
 readonly reviewAction=computed(()=>this.path()==='/case/letter' && this.selected()===5);
 readonly action=computed<FlowLink|null>(()=>{
   const i=this.selected(), step=(n:number,label:string):FlowLink=>({...this.steps()[n],label});
   if(this.path()==='/upload') return step(this.query()['step']==='policy'?0:this.query()['step']==='decision'?4:this.query()['returnTo']==='reply'?7:2,'Return to claim step');
   if(i===0) return this.policy()?step(1,'Continue to bill review'):{label:'Add your policy',route:'/upload',query:{type:'Policy document',step:'policy'}};
   if(i===1) return this.bill()?.reviewed ? step(this.journey.decided()?5:2,this.journey.decided()?'Review insurer deductions':'Continue to documents') : this.bill()?{label:'Review extracted bill',route:'/case/bill',fragment:'review'}:{label:'Add hospital bill',route:'/upload',query:{type:'Hospital bill'}};
   if(i===2) return this.journey.decided()||this.journey.lastReply()?.outcome==='asks_for_papers' ? {label:'Prepare response with current documents',route:'/case/letter',query:{step:'response',kind:this.journey.lastReply()?.outcome==='asks_for_papers'?'document_response':this.journey.suggestedLetter()}} : step(3,'Continue with current documents');
   if(i===3) return this.journey.decided()||this.journey.timeline().some(e=>e.kind==='claim_sent') ? step(4,'Check insurer response') : {label:'Record your submission',route:'/case/letter',query:{step:'submit',kind:'cover_letter'},fragment:'sent'};
   if(i===4) return this.journey.decided()?step(this.bill()?.reviewed?5:1,this.bill()?.reviewed?'Review decision & prepare response':'Review bill before deductions'):{label:'Check insurer response',route:'/case/detail',query:{step:'decision'}};
   if(i===5) return this.reviewAction()?step(6,'Continue to send follow-up'):{label:'Review the editable letter',route:'/case/letter',query:{step:'response',kind:this.journey.lastReply()?.outcome==='asks_for_papers'?'document_response':this.journey.suggestedLetter()}};
   if(i===6) return this.steps()[6].done?step(7,'Continue to insurer reply'):{...this.steps()[6],label:'Record when you sent it',query:{step:'send',kind:this.query()['kind']??this.journey.suggestedLetter()}};
   if(i===7) return this.journey.lastReply() && this.steps()[7].done ? step(this.journey.lastReply()?.outcome==='asks_for_papers'?2:this.journey.decided()?8:4,this.journey.lastReply()?.outcome==='asks_for_papers'?'Review requested documents':this.journey.decided()?'Continue to outcome':'Wait for a decision'):{label:'Add the insurer reply',route:'/case/reply',fragment:'add'};
   return this.journey.closed()?{label:'Back to all claims',route:'/case'}:{label:'Record outcome or close claim',route:'/case/detail',query:{step:'outcome'},fragment:'record-outcome'};
 });
 readonly messageTitle=computed(()=>this.selected()===1&&this.bill()?.reviewed?'Bill review saved':this.selected()===6&&this.steps()[6].done?'Follow-up recorded as sent':this.selected()===8&&this.journey.closed()?'Claim closed by you':'Your next action');
 readonly note=computed(()=>this.selected()===1&&this.bill()?.reviewed ? this.journey.decided()?'Bill checked. Ready to examine the insurer’s decision. Your earlier submission remains recorded.':'Your changes are saved. Next, review the supporting documents.' : this.selected()===2?'Missing documents stay visible. You may prepare a draft with the documents you have.':this.selected()===5?'Review the findings and edit the draft. Continuing does not send the letter.':this.selected()===6?'Send through your insurer’s channel, then record it here. Downloading is not sending.':this.journey.flow().note);
 params(link:FlowLink){return {workspace:this.workspace.mode(),...link.query};}
 reviewAndContinue(){if(!this.journey.draftReady())return;this.journey.markResponseReviewed();const link=this.steps()[6];this.router.navigate([link.route],{queryParams:this.params({...link,query:{...link.query,kind:this.query()['kind']??this.journey.suggestedLetter()}}),fragment:'sent'});}
}
