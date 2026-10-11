import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { AgentProgressComponent } from '../../shared/agent-progress.component';
import { AgentStep } from '../../models/models';

const MAX_BYTES = 20 * 1024 * 1024;

interface UploadItem {
  id: number;
  name: string;
  sizeKb: number;
  steps: AgentStep[];
  done: boolean;
  detectedType?: string;
  pages?: number;
  message?: string;
  error?: string;
}

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule, AgentProgressComponent],
  templateUrl: './upload.component.html',
  styles: `
    .drop { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 16px; text-align: center;
            border: 2px dashed #b9c8de; border-radius: var(--cn-radius); background: #fff; cursor: pointer; }
    .drop.over { border-color: var(--cn-primary); background: var(--cn-primary-soft); }
    .drop mat-icon { font-size: 48px; width: 48px; height: 48px; color: var(--cn-primary); }
    .types { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
    .file-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
    .file-head mat-icon { color: #c5221f; }
    .error { color: var(--cn-bad); margin: 0; }
  `,
})
export class UploadComponent {
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);

  items = signal<UploadItem[]>([]);
  dragOver = signal(false);
  private nextId = 1;

  readonly acceptedTypes = ['Policy wording or schedule', 'Hospital bill', 'Discharge summary', 'Settlement or rejection letter'];

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
    for (const file of Array.from(files ?? [])) {
      const id = this.nextId++;
      const item: UploadItem = { id, name: file.name, sizeKb: Math.round(file.size / 1024), steps: [], done: false };
      if (file.type !== 'application/pdf') {
        item.error = 'Only PDF files are supported for now.';
      } else if (file.size > MAX_BYTES) {
        item.error = 'This file is larger than 20 MB.';
      }
      this.items.update((list) => [item, ...list]);
      if (!item.error) this.process(id, file);
    }
  }

  private process(id: number, file: File): void {
    this.api.uploadDocument(file).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (event) => {
        if (event.type === 'done' && event.detectedType === 'Policy document') this.api.refreshPolicy();
        this.patch(id, (it) => event.type === 'step'
        ? { ...it, steps: [...it.steps, { agent: 'Ingestion', label: event.label }] }
        : { ...it, done: true, detectedType: event.detectedType, pages: event.pages, message: event.message });
      },
      error: (e) => this.patch(id, (it) => ({ ...it, error: e?.error?.detail ?? 'Upload failed. Please try again.' })),
    });
  }

  private patch(id: number, fn: (it: UploadItem) => UploadItem): void {
    this.items.update((list) => list.map((it) => (it.id === id ? fn(it) : it)));
  }
}
