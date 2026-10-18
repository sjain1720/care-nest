import { Component, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { JourneyService } from '../../services/journey.service';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService, isLive } from '../../services/api.service';
import { Bill, BillCategory, BillReview, ClaimCase } from '../../models/models';
import { todayIso } from '../../shared/claim-diary';
import { InrPipe } from '../../shared/inr.pipe';
import { TranslatePipe } from '../../shared/translate.pipe';

const CATEGORIES: { value: BillCategory; label: string }[] = [
  { value: 'room', label: 'Room' }, { value: 'icu', label: 'ICU' }, { value: 'nursing', label: 'Nursing' },
  { value: 'doctor', label: 'Doctor visits' }, { value: 'surgery', label: 'Surgery / operation theatre' },
  { value: 'anaesthesia', label: 'Anaesthesia' }, { value: 'procedure', label: 'Procedure' }, { value: 'pharmacy', label: 'Medicines' },
  { value: 'consumables', label: 'Consumables' }, { value: 'implants', label: 'Implants' }, { value: 'investigations', label: 'Tests and scans' },
  { value: 'equipment', label: 'Equipment' }, { value: 'food', label: 'Food' }, { value: 'admin', label: 'Admin / registration' },
  { value: 'other', label: 'Other' },
];
const KNOWN = new Set<string>(CATEGORIES.map((c) => c.value));

interface Row { description: string; category: BillCategory; amount: number | null; page: number }

/** "Check what we read": the family confirms or corrects the bill reading before relying on the checks or writing to the insurer. */
@Component({
  selector: 'app-bill-review',
  standalone: true,
  imports: [RouterLink, DatePipe, FormsModule, MatButtonModule, MatIconModule, InrPipe, TranslatePipe],
  template: `
    <section class="card review" id="review" [class.todo]="!bill().reviewed" aria-labelledby="review-title">
      @if (!editing()) {
        <div class="rv-head">
          <span class="rv-icon"><mat-icon>{{ bill().reviewed ? 'verified' : 'fact_check' }}</mat-icon></span>
          <div class="rv-text">
            <h2 id="review-title">{{ (bill().reviewed ? 'You checked what we read' : 'Check what we read from your bill') | t }}</h2>
            <p class="muted small">
              @if (bill().reviewed) {
                {{ 'The checks below use the details you confirmed.' | t }}
              } @else {
                {{ 'Compare these with your paper bill before you rely on the checks below or write to the insurer.' | t }}
              }
            </p>
          </div>
        </div>
        <dl class="rv-grid">
          <div><dt>{{ 'Hospital' | t }}</dt><dd>{{ bill().hospital || '—' }}</dd></div>
          <div><dt>{{ 'Bill number' | t }}</dt><dd>{{ bill().billNumber || '—' }}</dd></div>
          <div><dt>{{ 'Bill date' | t }}</dt><dd>{{ bill().billDate ? (bill().billDate | date: 'd MMM y') : '—' }}</dd></div>
          <div><dt>{{ 'Patient' | t }}</dt><dd>{{ claim()?.patient?.name || '—' }}</dd></div>
          <div><dt>{{ 'Hospital stay' | t }}</dt><dd>@if (claim()?.admissionDate) { {{ claim()!.admissionDate | date: 'd MMM' }} – {{ claim()!.dischargeDate ? (claim()!.dischargeDate | date: 'd MMM y') : '?' }} } @else { — }</dd></div>
          <div><dt>{{ 'Bill total' | t }}</dt><dd>{{ bill().total | inr }}</dd></div>
          <div><dt>{{ 'Charges read' | t }}</dt><dd>{{ bill().items.length }}</dd></div>
        </dl>
        @if (bill().unreadableLines) {
          <p class="rv-warn"><mat-icon>visibility_off</mat-icon>{{ bill().unreadableLines }} {{ "line(s) on the bill couldn't be read. Add them yourself if you can read them." | t }}</p>
        }
        <div class="row">
          @if (!bill().reviewed) {
            <button mat-flat-button class="btn-teal" type="button" (click)="confirm()" [disabled]="saving()"><mat-icon>check</mat-icon> {{ 'Yes, these are right' | t }}</button>
            <button mat-stroked-button class="btn-amber" type="button" (click)="startEditing()"><mat-icon>edit</mat-icon> {{ 'Correct something' | t }}</button>
          } @else {
            <button mat-button class="btn-sky" type="button" (click)="startEditing()"><mat-icon>edit</mat-icon> {{ 'Edit the details' | t }}</button>
          }
        </div>
      } @else {
        <form (ngSubmit)="save()">
          <h2 id="review-title">{{ 'Correct what we read' | t }}</h2>
          <p class="muted small">{{ 'Change anything that differs from your paper bill. We then run every check again on your values.' | t }}</p>
          <div class="rv-fields">
            <label>{{ 'Hospital' | t }}<input name="hospital" maxlength="120" [(ngModel)]="form.hospital"></label>
            <label>{{ 'Bill number' | t }}<input name="billNumber" maxlength="60" [(ngModel)]="form.billNumber"></label>
            <label>{{ 'Bill date' | t }}<input type="date" name="billDate" [max]="today" [(ngModel)]="form.billDate"></label>
            <label>{{ 'Patient' | t }}<input name="patientName" maxlength="60" [(ngModel)]="form.patientName"></label>
            <label>{{ 'Admitted on' | t }}<input type="date" name="admissionDate" [max]="today" [(ngModel)]="form.admissionDate"></label>
            <label>{{ 'Discharged on' | t }}<input type="date" name="dischargeDate" [max]="today" [(ngModel)]="form.dischargeDate"></label>
            <label>{{ 'Bill total (₹)' | t }}<input type="number" name="statedTotal" min="0" step="1" [(ngModel)]="form.statedTotal"></label>
          </div>

          <h3>{{ 'Charges' | t }}</h3>
          <div class="rv-items" role="table" [attr.aria-label]="'Charges' | t">
            <div class="rv-row rv-th" role="row">
              <span role="columnheader">{{ 'Item' | t }}</span><span role="columnheader">{{ 'Type' | t }}</span>
              <span role="columnheader">{{ 'Amount (₹)' | t }}</span><span role="columnheader">{{ 'Page' | t }}</span><span></span>
            </div>
            @for (r of rows(); track $index; let i = $index) {
              <div class="rv-row" role="row">
                <input [name]="'desc' + i" maxlength="200" [(ngModel)]="r.description" [attr.aria-label]="'Item' | t" required>
                <select [name]="'cat' + i" [(ngModel)]="r.category" [attr.aria-label]="'Type' | t">
                  @for (c of categories; track c.value) { <option [value]="c.value">{{ c.label | t }}</option> }
                </select>
                <input type="number" [name]="'amt' + i" min="0" step="1" [(ngModel)]="r.amount" [attr.aria-label]="'Amount (₹)' | t" required>
                <input type="number" [name]="'page' + i" min="1" step="1" [(ngModel)]="r.page" [attr.aria-label]="'Page' | t">
                <button mat-icon-button type="button" (click)="removeRow(i)" [attr.aria-label]="('Remove' | t) + ': ' + r.description"><mat-icon>delete</mat-icon></button>
              </div>
            }
          </div>
          <button mat-button class="btn-violet" type="button" (click)="addRow()"><mat-icon>add</mat-icon> {{ 'Add a charge' | t }}</button>
          <p class="small" [class.rv-diff]="difference() !== 0">
            {{ 'Charges add up to' | t }} <strong>{{ itemsSum() | inr }}</strong>.
            @if (difference() !== 0 && form.statedTotal !== null) { {{ 'The bill total is' | t }} <strong>{{ form.statedTotal | inr }}</strong> ({{ 'difference' | t }} {{ difference() | inr }}). }
          </p>
          @if (error()) { <p class="rv-error" role="alert">{{ error()! | t }}</p> }
          @if (!live) { <p class="muted small">{{ 'Demo: your corrections are kept in this browser. With your own documents, every check is run again on them.' | t }}</p> }
          <div class="row">
            <button mat-flat-button type="submit" [disabled]="saving()">{{ (saving() ? 'Saving…' : 'Save and check again') | t }}</button>
            <button mat-button type="button" (click)="editing.set(false)">{{ 'Cancel' | t }}</button>
          </div>
        </form>
      }
      @if (bill().reviewed && !editing()) {
        <div class="saved-next" role="status"><strong>Bill review saved</strong><p>{{journey.decided() ? 'Bill checked. Ready to examine the insurer’s decision.' : 'Your changes are saved. Next, review the supporting documents.'}}</p>
        <a mat-flat-button [routerLink]="journey.decided() ? '/case/settlement' : '/case/detail'" [queryParams]="{workspace:api.workspace.mode(),step:journey.decided() ? 'response' : 'documents'}">{{journey.decided() ? 'Review insurer deductions' : 'Continue to documents'}} →</a></div>
      }
    </section>
  `,
  styles: `
    .saved-next{margin-top:16px;padding:16px;border-radius:10px;background:var(--cn-primary-soft)}.saved-next p{margin:4px 0 12px;font-size:.9rem}
    .review.todo { border-color: var(--cn-c3-line); background: linear-gradient(135deg, var(--cn-c3-soft), var(--cn-surface) 70%); }
    .rv-head { display: flex; gap: 12px; align-items: flex-start; }
    .rv-icon { flex: none; width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center; background: var(--cn-c1-soft); color: var(--cn-c1-ink); }
    .todo .rv-icon { background: var(--cn-c3-soft); color: var(--cn-c3-ink); }
    .rv-text h2 { margin: 0; }
    .rv-text p { margin: 2px 0 0; }
    .rv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px 16px; margin: 14px 0 10px; }
    .rv-grid dt { font-size: .75rem; color: var(--cn-muted); text-transform: uppercase; letter-spacing: .04em; }
    .rv-grid dd { margin: 0; font-weight: 600; color: var(--cn-strong); overflow-wrap: anywhere; }
    .rv-warn { display: flex; align-items: center; gap: 6px; margin: 0 0 10px; color: var(--cn-warn); font-size: .88rem; }
    .rv-warn mat-icon { font-size: 18px; width: 18px; height: 18px; }
    form h2 { margin: 0; }
    form h3 { margin: 16px 0 6px; font-size: .95rem; }
    .rv-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px 12px; margin-top: 10px; }
    label { display: flex; flex-direction: column; gap: 4px; font-size: .82rem; color: var(--cn-muted); }
    input, select { min-height: 40px; padding: 0 8px; font: inherit; font-size: .92rem; color: var(--cn-ink); border: 1px solid var(--cn-border);
                    border-radius: 8px; background: var(--cn-field); min-width: 0; width: 100%; }
    .rv-items { display: grid; gap: 6px; }
    .rv-row { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr) minmax(90px, 1fr) 64px 40px; gap: 6px; align-items: center; }
    .rv-th { font-size: .75rem; color: var(--cn-muted); text-transform: uppercase; letter-spacing: .04em; }
    .rv-diff { color: var(--cn-warn); }
    .rv-error { color: var(--cn-bad); }
    @media (max-width: 599px) {
      .rv-th { display: none; }
      .rv-row { grid-template-columns: minmax(0, 1fr) 88px 40px; padding: 8px 0; border-top: 1px solid var(--cn-border); }
      .rv-row input:first-child { grid-column: 1 / -1; }
      .rv-row select { grid-column: 1 / -1; }
    }
  `,
})
export class BillReviewComponent {
  readonly api = inject(ApiService);
  readonly journey = inject(JourneyService);
  readonly bill = input.required<Bill>();
  readonly claim = input<ClaimCase | null | undefined>(null);

  readonly live = isLive('bill');
  readonly today = todayIso();
  readonly categories = CATEGORIES;
  readonly editing = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly rows = signal<Row[]>([]);
  form = { hospital: '', billNumber: '', billDate: '', patientName: '', admissionDate: '', dischargeDate: '', statedTotal: null as number | null };

  // Plain methods (not computed), so the sum follows the form fields as the family types.
  itemsSum(): number {
    return this.rows().reduce((s, r) => s + (Number(r.amount) || 0), 0);
  }
  difference(): number {
    return this.form.statedTotal === null ? 0 : Math.round(this.itemsSum() - this.form.statedTotal);
  }

  startEditing(): void {
    const b = this.bill();
    const c = this.claim();
    this.form = { hospital: b.hospital ?? '', billNumber: b.billNumber ?? '', billDate: b.billDate ?? '', patientName: c?.patient?.name ?? '',
      admissionDate: c?.admissionDate ?? '', dischargeDate: c?.dischargeDate ?? '', statedTotal: b.total ?? null };
    this.rows.set(b.items.map((i) => ({ description: i.description, category: toCategory(i.category), amount: i.amount, page: i.page || 1 })));
    this.error.set(null);
    this.editing.set(true);
  }

  addRow(): void {
    this.rows.update((list) => [...list, { description: '', category: 'other', amount: null, page: 1 }]);
  }

  removeRow(index: number): void {
    this.rows.update((list) => list.filter((_, i) => i !== index));
  }

  /** "Yes, these are right": confirm the reading as it is. */
  confirm(): void {
    this.startEditing();
    this.editing.set(false);
    this.submit();
  }

  save(): void {
    if (this.rows().some((r) => !r.description.trim() || r.amount === null || r.amount < 0)) {
      this.error.set('Every charge needs a description and an amount (0 or more).');
      return;
    }
    this.submit(() => this.editing.set(false));
  }

  private submit(done?: () => void): void {
    const f = this.form;
    const review: BillReview = {
      ...(f.hospital.trim() ? { hospital: f.hospital.trim() } : {}),
      billNumber: f.billNumber.trim(),
      ...(f.billDate ? { billDate: f.billDate } : {}),
      ...(f.patientName.trim() ? { patientName: f.patientName.trim() } : {}),
      ...(f.admissionDate ? { admissionDate: f.admissionDate } : {}),
      ...(f.dischargeDate ? { dischargeDate: f.dischargeDate } : {}),
      ...(f.statedTotal !== null && f.statedTotal >= 0 ? { statedTotal: Number(f.statedTotal) } : {}),
      items: this.rows().map((r) => ({ description: r.description.trim(), category: r.category, amount: Number(r.amount), page: Number(r.page) || 1 })),
    };
    this.saving.set(true);
    this.error.set(null);
    this.api.reviewBill(review).subscribe({
      next: () => {
        this.saving.set(false);
        done?.();
      },
      error: (e) => {
        this.saving.set(false);
        this.error.set(e?.error?.detail?.[0]?.msg ?? e?.error?.detail ?? 'Could not save. Please check the values and try again.');
      },
    });
  }
}

/** The sample bill's categories are capitalised ("Room"); the backend uses lower case. */
function toCategory(value: string): BillCategory {
  const v = (value || '').toLowerCase();
  return (KNOWN.has(v) ? v : 'other') as BillCategory;
}
