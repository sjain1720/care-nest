import { Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { A11yModule } from '@angular/cdk/a11y';
import { MatIconModule } from '@angular/material/icon';
import { VisitorProfileService } from '../services/visitor-profile.service';
@Component({selector:'app-visitor-welcome',standalone:true,imports:[FormsModule,A11yModule,MatIconModule],
 template:`@if (!profile.loaded() || !profile.name()) {
 <div class="workspace-overlay"><section class="workspace-dialog" role="dialog" aria-modal="true" aria-labelledby="visitor-title" cdkTrapFocus [cdkTrapFocusAutoCapture]="true">
 <p class="eyebrow">WELCOME TO CARENEST</p><h1 id="visitor-title">Your partner in understanding health insurance and claims.</h1>
 @if (!profile.loaded()) { <p role="status">Opening your guest session…</p>@if(profile.error()){<p role="alert">{{profile.error()}}</p><button type="button" class="action-link" (click)="retry()">Retry</button>} }
 @else { <form (ngSubmit)="save()"><label for="visitor-name"><strong>What should Nessi call you?</strong></label><p>A name or nickname is enough.</p>
 <input id="visitor-name" name="displayName" type="text" autocomplete="given-name" maxlength="60" required [(ngModel)]="name" [disabled]="busy()" cdkFocusInitial style="box-sizing:border-box;width:100%;padding:14px;border:1px solid var(--cn-border);border-radius:12px;font:inherit">
 <p class="small muted">Explore a fictional family example or use your own documents. This is a temporary guest session, not a registered account.</p>
 <button class="action-link" type="submit" [disabled]="!name.trim() || busy()">{{busy() ? 'Saving…' : 'Continue'}} <mat-icon>arrow_forward</mat-icon></button>
 @if(error()){<p role="alert">{{error()}}</p>}</form> }
 </section></div> }`})
export class VisitorWelcomeComponent {
 readonly profile=inject(VisitorProfileService); name='';readonly busy=signal(false);readonly error=signal('');
 constructor(){this.retry();effect(()=>{if(this.profile.loaded()&&!this.profile.name())setTimeout(()=>document.getElementById('visitor-name')?.focus(),0);});}
 retry(){this.profile.load().catch(()=>undefined);}
 async save(){this.busy.set(true);this.error.set('');try{await this.profile.save(this.name);}catch(e){this.error.set((e as Error).message);}finally{this.busy.set(false);}}
}
