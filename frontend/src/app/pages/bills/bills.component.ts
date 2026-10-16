import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { InrPipe } from '../../shared/inr.pipe';
import { EmptyStateComponent } from '../../shared/page-states.component';
@Component({ standalone: true, imports: [RouterLink, DatePipe, MatIconModule, InrPipe, EmptyStateComponent],
 template: `<div class="page"><header class="section-heading"><div><p class="eyebrow">YOUR DOCUMENTS</p><h1>Hospital bills</h1><p class="muted">Review the bill we read, inspect its source and check the charges.</p></div><a class="action-link" routerLink="/upload" [queryParams]="{type:'Hospital bill'}"><mat-icon>upload_file</mat-icon> Add a bill</a></header>
 @if (bill(); as b) { <section class="card document-list"><header><h2>Current hospital bill</h2><span class="pill tone-info">{{ b.items.length }} charges read</span></header><div class="document-list-row"><span class="round-icon"><mat-icon>local_hospital</mat-icon></span><div class="grow"><h3>{{ b.hospital }}</h3><p class="muted small">{{ b.billNumber || 'Bill number not recorded' }} · {{ b.billDate | date:'d MMM y' }}</p></div><strong class="bill-amount">{{ b.total | inr }}</strong><a class="action-link" routerLink="/case/bill">Check bill <mat-icon>arrow_forward</mat-icon></a></div><p class="small muted">Reading a bill does not mean the insurer has approved its charges.</p></section> }
 @if (documents().length) { <section class="card document-list"><header><h2>Original bill files</h2><span>{{ documents().length }} available</span></header>@for (doc of documents(); track doc.id) { <div class="document-list-row"><span class="round-icon"><mat-icon>{{ doc.id.startsWith('img-') ? 'image' : 'description' }}</mat-icon></span><div class="grow"><strong>{{ doc.name }}</strong><p class="small muted">{{ doc.pages }} pages read</p></div>@if (doc.docUrl) { <a [href]="doc.docUrl" target="_blank" rel="noopener">Open original ↗</a> }</div> }</section> }
 @if (!bill() && !documents().length) { <app-empty-state icon="receipt_long" title="No hospital bills yet" text="Add a bill as a PDF or a clear photo. Your personal files remain separate from Shubham's example." action="Add a hospital bill" route="/upload" /> }
 </div>`,
})
export class BillsComponent {
 private api = inject(ApiService);
 readonly bill = toSignal(this.api.getBill());
 readonly claim = toSignal(this.api.getCase());
 readonly documents = computed(() => (this.claim()?.documents ?? []).filter(d => d.type === 'Hospital bill'));
}
