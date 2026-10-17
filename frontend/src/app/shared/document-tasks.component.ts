import { Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { ApiService } from '../services/api.service';
import { ClaimDocuments, DocumentTask } from '../models/models';

@Component({selector:'app-document-tasks',standalone:true,imports:[FormsModule,RouterLink,MatButtonModule],template:`
 <section aria-label="Document tasks">
 @if(error()){<p role="alert">{{error()}} <button mat-button (click)="load()">Retry</button></p>}
 @if(state();as data){
 @for(task of tasks();track task.id){
 <article class="task" [id]="'doc-task-'+task.id">
 <div class="task-head"><div><strong>{{task.label}}</strong><p>Get it from: {{task.source}}</p><p>{{task.why}}</p></div>
 <a mat-stroked-button routerLink="/upload" [queryParams]="uploadParams(task)">Upload for this item</a></div>
 @if(task.checklistId){<p class="status">Checklist: {{task.checklistStatus === 'collected' ? 'You have it' : task.checklistStatus === 'requested' ? 'You requested it' : 'Still needed'}}</p><div class="row"><button mat-button (click)="markHave(task,'collected')">I have it</button><button mat-button (click)="markHave(task,'requested')">I've requested it</button>@if(task.checklistStatus!=='missing'){<button mat-button (click)="markHave(task,'missing')">Mark missing</button>}</div>}
 <p class="status">{{task.notApplicable ? 'Marked not applicable by you' : task.reviewed ? 'Document linked · checked by you' : task.documents.length ? 'Uploaded · review still needed' : 'No document linked'}} · {{task.documents.length}} file(s)</p>
 @for(doc of task.documents;track doc.id){<div class="file"><a [href]="doc.docUrl" target="_blank" rel="noopener">{{doc.name}}</a><button mat-button (click)="unlink(task,doc.id)" [disabled]="saving()">Unlink</button></div>}
 <details><summary>Link an existing file or explain a missing item</summary>
 @for(doc of documents();track doc.id){<label class="file"><input type="checkbox" [checked]="linked(task,doc.id)" (change)="link(task,doc.id,$any($event.target).checked)" [disabled]="saving()">{{doc.name}}</label>}
 <label class="note">Your note / reason if not applicable<input [ngModel]="task.note" (ngModelChange)="task.note=$event" maxlength="500"></label>
 <button mat-stroked-button (click)="save(task,false,true)" [disabled]="saving()||!task.note.trim()">Mark not applicable with this reason</button>
 </details>
 <div class="row"><button mat-stroked-button (click)="save(task,true,false)" [disabled]="saving()||!task.documents.length">I checked the linked document</button>
 @if(task.reviewed||task.notApplicable){<button mat-button (click)="save(task,false,false)" [disabled]="saving()">Needs another review</button>}</div>
 </article>
 } @empty {<p>No itemized insurer requests are available yet. Review the original reply before assuming which papers are required.</p>}
 @if(group()==='reply'){<p class="hint">Uploading does not prove an item meets the insurer's request. Review each linked file. You can draft a response while items are still pending.</p>
 <a mat-flat-button routerLink="/case/letter" [queryParams]="{workspace:api.workspace.mode(),kind:'document_response'}">Prepare response with current documents →</a>}
 } @else if(!error()){<p role="status">Opening document tasks…</p>}
 </section>
`,styles:`
 :host{display:block;min-width:0}.task{scroll-margin-top:calc(var(--cn-topbar-h) + 16px);border-top:1px solid var(--cn-border);padding:16px 0}.task-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.task-head div{min-width:0;flex:1}.task-head p,.hint,.status{font-size:.83rem;color:var(--cn-muted);margin:5px 0}.task-head a{flex:none}.file{display:flex;align-items:center;gap:8px;padding:6px 0;overflow-wrap:anywhere}.file input{width:20px;height:20px;flex:none}.row{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}summary{cursor:pointer;padding:10px 0;font-size:.85rem}.note{display:block;font-size:.85rem}.note input{display:block;width:100%;box-sizing:border-box;min-height:44px;padding:8px;border:1px solid var(--cn-border);border-radius:8px;background:var(--cn-field);color:var(--cn-ink);font:inherit;margin:5px 0 8px}
 @media(max-width:599px){.task-head{flex-direction:column}.task-head a{align-self:flex-start}}
`})
export class DocumentTasksComponent {
 readonly group=input<'reply'|'checklist'>('checklist');readonly api=inject(ApiService);private destroy=inject(DestroyRef);
 readonly state=signal<ClaimDocuments|null>(null);readonly error=signal('');readonly saving=signal(false);private loadVersion=0;
 readonly tasks=computed(()=>this.state()?.tasks.filter(t=>t.kind===this.group())??[]);readonly documents=signal<import('../models/models').CaseDocument[]>([]);
 constructor(){this.api.getCase().pipe(takeUntilDestroyed()).subscribe(c=>{this.documents.set(c?.documents??[]);if(!c)this.state.set(null);this.load();});}
 load(){const version=++this.loadVersion;const workspace=this.api.workspace.mode();this.api.getDocumentTasks().pipe(takeUntilDestroyed(this.destroy)).subscribe({next:s=>{if(version===this.loadVersion && this.api.workspace.mode()===workspace){this.state.set(s);this.error.set('');}},error:e=>this.error.set(e?.error?.detail??'Could not open document tasks.')});}
 uploadParams(task:DocumentTask){return {workspace:this.api.workspace.mode(),claimKey:this.state()?.claimKey,task:task.id,type:task.checklistId==='c4'?'Hospital bill':task.checklistId==='c3'?'Discharge summary':'Other',returnTo:task.kind==='reply'?'reply':'documents'};}
 linked(task:DocumentTask,id:string){return task.documents.some(d=>d.id===id);}
 markHave(task:DocumentTask,status:'collected'|'requested'|'missing'){if(task.checklistId)this.api.updateChecklistItem(task.checklistId,status).pipe(takeUntilDestroyed(this.destroy)).subscribe({error:()=>this.error.set('Could not save checklist status.')});}
 link(task:DocumentTask,id:string,checked:boolean){const ids=task.documents.map(d=>d.id).filter(i=>i!==id);if(checked)ids.push(id);this.persist(task,ids,false,false);}
 unlink(task:DocumentTask,id:string){this.link(task,id,false);}
 save(task:DocumentTask,reviewed:boolean,notApplicable:boolean){this.persist(task,task.documents.map(d=>d.id),reviewed,notApplicable);}
 private persist(task:DocumentTask,ids:string[],reviewed:boolean,notApplicable:boolean){const state=this.state();if(!state)return;this.saving.set(true);const mode=this.api.workspace.mode();this.api.updateDocumentTask(task.id,{expectedFingerprint:state.fingerprint,claimKey:state.claimKey,documentIds:ids,reviewed,notApplicable,note:task.note}).pipe(takeUntilDestroyed(this.destroy)).subscribe({next:s=>{if(mode===this.api.workspace.mode())this.state.set(s);this.saving.set(false);},error:e=>{this.error.set(e?.error?.detail??'Could not save task.');this.saving.set(false);}});}
}
