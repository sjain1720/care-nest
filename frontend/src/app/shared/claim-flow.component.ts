import { Component, computed, inject, input } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { filter, map } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { ApiService } from '../services/api.service';
import { WorkspaceService } from '../services/workspace.service';
import { FLOW_STAGES, resolveClaimFlow } from './claim-flow';

@Component({selector:'app-claim-flow',standalone:true,imports:[RouterLink,MatButtonModule],template:`
 @if (visible()) {
 @if (!footer()) {
 <a mat-button routerLink="/case" [queryParams]="{workspace:workspace.mode()}">← All claims</a>
 <nav class="flow no-print" aria-label="Claim workflow">
 @for (label of labels; track label; let i=$index) {
 <a [routerLink]="destination(i)" [queryParams]="params(i)" [attr.aria-current]="state().stage === i ? 'step' : null"><span>{{ i+1 }}</span>{{ label }}</a>
 }
 </nav>
 } @else {
 <aside class="flow-next card no-print" aria-label="Next claim action">
 <div><strong>Next step</strong><p>{{state().note}}</p></div>
 <a mat-flat-button [routerLink]="state().next.route" [queryParams]="nextParams()" [fragment]="state().next.fragment">{{state().next.label}} →</a>
 @if (path()==='/case/letter') { <a mat-button routerLink="/case/reply" [queryParams]="{workspace:workspace.mode()}">I already have a reply</a> }
 <a mat-button routerLink="/case/detail" [queryParams]="{section:'overview',workspace:workspace.mode()}">Back to claim overview</a>
 </aside>
 }
 }
`,styles:`
 :host{display:block;min-width:0}.flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:12px 0 20px}
 .flow a{display:flex;gap:7px;align-items:center;padding:10px 8px;border-bottom:2px solid var(--cn-border);font-size:.84rem;color:var(--cn-muted);text-decoration:none;min-height:44px}
 .flow a[aria-current]{border-color:var(--cn-primary);color:var(--cn-strong);font-weight:700;background:var(--cn-primary-soft);border-radius:8px 8px 0 0}
 .flow span{border:1px solid currentColor;border-radius:50%;width:23px;height:23px;display:grid;place-items:center;flex:none}
 .flow-next{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:16px 0}.flow-next div{flex:1;min-width:200px}.flow-next p{font-size:.85rem;margin:4px 0;color:var(--cn-muted)}
 @media(max-width:599px){.flow{grid-template-columns:repeat(2,minmax(0,1fr))}.flow-next a{white-space:normal;max-width:100%;height:auto;min-height:44px}}
`})
export class ClaimFlowComponent {
 readonly footer=input(false);readonly workspace=inject(WorkspaceService);
 private api=inject(ApiService);private router=inject(Router);
 private url=toSignal(this.router.events.pipe(filter(e=>e instanceof NavigationEnd),map(()=>this.router.url)),{initialValue:this.router.url});
 readonly path=computed(()=>this.url().split('?')[0].split('#')[0]);
 private query=computed(()=>this.router.parseUrl(this.url()).queryParams);
 private c=toSignal(this.api.getCase());private bill=toSignal(this.api.getBill());private settlement=toSignal(this.api.getSettlement());
 readonly visible=computed(()=>this.workspace.mode()!=='general' && (this.path().startsWith('/case/')||this.path()==='/upload'||(this.path()==='/case' && (!!this.query()['section'] || ['checklist','documents','dispute-papers','diary','overview','next-steps'].includes(this.router.parseUrl(this.url()).fragment??'')))));
 readonly state=computed(()=>resolveClaimFlow(this.c(),this.bill(),!!this.settlement()||!!this.c()?.rejection,this.path(),this.query()['section']??(this.router.parseUrl(this.url()).fragment === 'checklist' ? 'documents' : null),this.query()['outcome']==='1',this.query()['kind']??null));
 readonly labels=FLOW_STAGES;
 destination(i:number){return i===1 ? (this.settlement()||this.c()?.rejection ? '/case/settlement':'/case/letter') : i===2 ? '/case/reply':'/case/detail';}
 params(i:number){return {workspace:this.workspace.mode(),...(i===0?{section:'documents'}:i===3?{section:'history',outcome:'1'}:i===1&&!this.settlement()&&!this.c()?.rejection?{kind:'cover_letter'}:{})};}
 nextParams(){return {workspace:this.workspace.mode(),...this.state().next.query};}
}
