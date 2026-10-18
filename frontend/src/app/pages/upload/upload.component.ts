import { ClaimDocuments } from '../../models/models';
import { WorkspaceService } from '../../services/workspace.service';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { TranslatePipe } from '../../shared/translate.pipe';
import { MatIconModule } from '@angular/material/icon';
import { ApiService, DOC_TYPES, DocType } from '../../services/api.service';
import { ChatService } from '../../services/chat.service';
import { JourneyService } from '../../services/journey.service';
import { AgentProgressComponent } from '../../shared/agent-progress.component';
import { NextStep, NextStepsComponent } from '../../shared/next-steps.component';
import { AgentStep } from '../../models/models';

const MAX_BYTES = 20 * 1024 * 1024;
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ACCEPTED_TYPES = ['application/pdf', ...PHOTO_TYPES];

const TYPE_LABELS: Partial<Record<DocType, string>> = {
  auto: 'Let CareNest work it out',
  'Settlement letter': "Insurer's payment letter (settlement)",
  'Rejection letter': "Insurer's refusal letter",
  'Insurer reply': "Any insurer response (request, approval or rejection)",
};

interface UploadItem {
  id: number;
  name: string;
  sizeKb: number;
  photo: boolean;
  steps: AgentStep[];
  done: boolean;
  detectedType?: string;
  pages?: number;
  message?: string;
  error?: string;
  startedAt?: number;
}

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [FormsModule, RouterLink, MatButtonModule, MatIconModule, AgentProgressComponent, NextStepsComponent, TranslatePipe],
  templateUrl: './upload.component.html',
  styles: `
    .drop { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 16px; text-align: center;
            border: 2px dashed var(--cn-border-strong); border-radius: var(--cn-radius); background: var(--cn-surface); cursor: pointer; }
    .drop.over { border-color: var(--cn-primary); background: var(--cn-primary-soft); }
    .drop mat-icon { font-size: 48px; width: 48px; height: 48px; color: var(--cn-primary); }
    .types { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
    .file-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
    .file-head mat-icon { color: var(--cn-pdf); }
    .file-head .spacer { min-width: 0; overflow-wrap: anywhere; }
    #upload-results { scroll-margin-top: calc(var(--cn-topbar-h) + 16px); }
    #upload-results:empty { display: none; }
    .error { color: var(--cn-bad); margin: 0; }
    .type-select { min-height: 44px; padding: 0 10px; font: inherit; color: var(--cn-ink); border: 1px solid var(--cn-border); border-radius: 10px; background: var(--cn-field); }
    .photo-btn { display: none; align-items: center; justify-content: center; gap: 8px; width: 100%; min-height: 48px; margin: 0 0 12px; padding: 0 16px;
                 border-radius: 999px; border: 1px solid var(--cn-c1-line); background: var(--cn-c1-soft); color: var(--cn-c1-ink); font-weight: 600; cursor: pointer; }
    /* Phones and tablets: open the camera straight away. */
    @media (hover: none) and (pointer: coarse) { .photo-btn { display: flex; } }
  `,
})
export class UploadComponent {
  private api = inject(ApiService);
  readonly workspace = inject(WorkspaceService);
  readonly context = signal<ClaimDocuments|null>(null);
  readonly contextError = signal('');
  readonly replaceExisting = signal(false);
  readonly taskId = inject(ActivatedRoute).snapshot.queryParamMap.get('task') ?? undefined;
  readonly journeyStep = inject(ActivatedRoute).snapshot.queryParamMap.get('step');
  readonly returnTo = inject(ActivatedRoute).snapshot.queryParamMap.get('returnTo') === 'reply' ? 'reply' : 'documents';
  readonly targetTask = computed(()=>this.context()?.tasks.find(t=>t.id===this.taskId));
  readonly processing = computed(()=>this.items().some(it=>!it.done && !it.error));
  private loadContext(): void {
    const expected = this.routeKey;
    this.api.getDocumentTasks().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({next:data=>{
      if(expected && data.claimKey !== expected){this.contextError.set('This claim changed. Return to the claim documents before uploading.');return;}
      if(this.taskId && !data.tasks.some(t=>t.id===this.taskId)){this.contextError.set('This requested item changed. Return to the insurer reply.');return;}
      this.context.set(data);
    },error:()=>this.contextError.set('Could not open the selected claim. Return to its documents and retry.')});
  }
  private readonly routeKey = inject(ActivatedRoute).snapshot.queryParamMap.get('claimKey');
  returnRoute(){if(this.journeyStep==='policy')return '/policy';if(this.journeyStep==='decision')return '/case/reply';return this.returnTo === 'reply' ? '/case/reply' : '/case/detail';}
  returnQuery(){if(this.journeyStep==='policy')return {workspace:this.workspace.mode(),step:this.journeyStep};if(this.journeyStep==='decision')return {workspace:this.workspace.mode()};return this.returnTo === 'reply' ? {workspace:this.workspace.mode()} : {workspace:this.workspace.mode(),section:'documents'};}

  readonly chat = inject(ChatService);
  private destroyRef = inject(DestroyRef);

  items = signal<UploadItem[]>([]);
  readonly completedUpload = computed(() => this.items().some((it) => it.done));
  dragOver = signal(false);
  private hasPolicy = toSignal(this.api.getPolicy());
  readonly hasBill = toSignal(this.api.getBill());
  readonly hasSettlement = toSignal(this.api.getSettlement());
  private journey = inject(JourneyService);
  nextSteps = computed<NextStep[]>(() => [
    { text: 'Start with your policy papers. We read every page.', done: !!this.hasPolicy() },
    { text: 'Add the final hospital bill: a PDF, or a clear phone photo if the bill is one page.', done: !!this.hasBill() },
    { text: "Add any insurer response: a request for documents, approval or rejection.", done: !!this.hasSettlement() || !!this.journey.rejection() },
    { text: 'Wrote to the insurer and they answered? Add their reply too.', done: !!this.journey.lastReply() },
  ]);
  docType: DocType = 'auto';
  readonly docTypes = DOC_TYPES;
  readonly accept = ACCEPTED_TYPES.join(',');
  private nextId = 1;
  readonly now = signal(Date.now());

  readonly acceptedTypes = ['Policy papers', 'Hospital bill', 'Discharge summary', "Insurer's letter (payment or refusal)", "Insurer's reply"];

  constructor() {
    const timer = setInterval(() => this.now.set(Date.now()), 1000);
    this.destroyRef.onDestroy(() => clearInterval(timer));
    const wanted = inject(ActivatedRoute).snapshot.queryParamMap.get('type');
    if (wanted && (DOC_TYPES as readonly string[]).includes(wanted)) this.docType = wanted as DocType;
    this.loadContext();
  }

  uploadAction(type?: string): { label: string; route: string; fragment?: string } {
    if (type === 'Policy document') return { label: 'Ask about this policy', route: '/ask' };
    if (type === 'Hospital bill') return { label: 'Check this bill', route: '/case/bill', fragment: 'review' };
    if (type === 'Settlement letter' || type === 'Rejection letter') return { label: 'Explain this decision', route: '/case/settlement' };
    if (type === 'Insurer reply') return { label: 'Understand this reply', route: '/case/reply' };
    return { label: 'Review my claim documents', route: '/case/detail', fragment: 'documents' };
  }

  hasExistingDocument(): boolean { return this.docType === 'Hospital bill' ? !!this.hasBill() : this.docType === 'Settlement letter' ? !!this.hasSettlement() : this.docType === 'Rejection letter' ? !!this.journey.rejection() : false; }

  typeLabel(t: DocType): string {
    return TYPE_LABELS[t] ?? t;
  }

  onPick(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.addFiles(input.files);
    input.value = '';
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    this.addFiles(event.dataTransfer?.files ?? null);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(true);
  }

  private addFiles(files: FileList | null): void {
    if (!this.context() || this.contextError() || this.processing()) return;
    if (this.taskId && files && files.length > 1) { this.contextError.set('Choose one file at a time for a requested item.'); return; }
    for (const file of Array.from(files ?? [])) {
      const id = this.nextId++;
      const photo = PHOTO_TYPES.includes(file.type);
      const item: UploadItem = { id, name: file.name, sizeKb: Math.round(file.size / 1024), photo, steps: [], done: false };
      if (!ACCEPTED_TYPES.includes(file.type)) {
        item.error = 'Upload a PDF, or a photo (JPG, PNG or WebP).';
      } else if (photo && this.docType === 'Policy document') {
        item.error = 'Upload the policy as a PDF. Photos work for bills and letters.';
      } else if (file.size > MAX_BYTES) {
        item.error = 'This file is larger than 20 MB.';
      }
      this.items.update((list) => [item, ...list]);
      if (!item.error) this.process(id, file);
    }
    if (files?.length) requestAnimationFrame(() => {
      if (!this.destroyRef.destroyed) document.getElementById('upload-results')?.scrollIntoView({ block: 'start' });
    });
  }

  private process(id: number, file: File): void {
    this.patch(id, (it) => ({ ...it, startedAt: Date.now() }));
    this.api.uploadDocument(file, this.docType, {claimKey:this.context()!.claimKey,taskId:this.taskId,replaceExisting:this.replaceExisting()}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (event) => {
        if (event.type === 'done') {
          if (event.detectedType === 'Policy document') this.api.refreshPolicy();
          else this.api.refreshCase();
        }
        this.patch(id, (it) => event.type === 'step'
        ? { ...it, steps: [...it.steps, { agent: 'Ingestion', label: event.label }] }
        : { ...it, done: true, detectedType: event.detectedType, pages: event.pages, message: event.message });
      },
      error: (e) => this.patch(id, (it) => ({ ...it, error: e?.name === 'TimeoutError'
        ? 'Processing took too long. Check My policy before retrying this file; it may have finished on the server.'
        : e?.error?.detail ?? (e?.status === 0
          ? 'The connection was interrupted. Check My policy or My claim, then retry if your document is missing.'
          : 'Upload failed. Please try again.') })),
    });
  }

  elapsed(startedAt: number): number { return Math.max(0, Math.floor((this.now() - startedAt) / 1000)); }

  private patch(id: number, fn: (it: UploadItem) => UploadItem): void {
    this.items.update((list) => list.map((it) => (it.id === id ? fn(it) : it)));
  }
}
