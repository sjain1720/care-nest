import { Component, inject, input, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { Member, PolicyDetailsInput, PolicyFacts } from '../../models/models';

interface MemberRow {
  name: string;
  relation: string;
  age: number | null;
}

/** "Add or correct your policy details" – values from the policy schedule that a policy wording usually lacks. */
@Component({
  selector: 'app-policy-details-form',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatIconModule],
  template: `
    <form (ngSubmit)="save()" #f="ngForm">
      <p class="muted small" style="margin-top:0">Copy these from your <strong>policy schedule</strong> (the page with your name and policy number). We use them to work out waiting-period dates and room-rent limits.</p>
      <div class="fields">
        <label>Policy start date (first policy, if renewed without a break)
          <input type="date" name="startDate" [(ngModel)]="startDate" [max]="today">
        </label>
        <label>Sum insured (₹)
          <input type="number" name="sumInsured" min="1" step="1000" [(ngModel)]="sumInsured">
        </label>
        <label>Room-rent limit per day (₹)
          <input type="number" name="roomRent" min="1" step="100" [(ngModel)]="roomRentPerDay">
        </label>
        <label>Policy number
          <input type="text" name="policyNumber" maxlength="40" [(ngModel)]="policyNumber" autocomplete="off">
        </label>
      </div>

      <h3>Covered members</h3>
      @for (m of members(); track $index; let i = $index) {
        <div class="member-row">
          <input type="text" [name]="'name' + i" [(ngModel)]="m.name" placeholder="Name" maxlength="60" aria-label="Member name">
          <select [name]="'relation' + i" [(ngModel)]="m.relation" aria-label="Relation">
            @for (r of relations; track r) { <option [value]="r">{{ r }}</option> }
          </select>
          <input type="number" [name]="'age' + i" [(ngModel)]="m.age" min="0" max="120" placeholder="Age" aria-label="Age" class="age">
          <button mat-icon-button type="button" (click)="removeMember(i)" [attr.aria-label]="'Remove ' + (m.name || 'member')"><mat-icon>delete</mat-icon></button>
        </div>
      }
      <button mat-button type="button" (click)="addMember()" [disabled]="members().length >= 10"><mat-icon>person_add</mat-icon> Add member</button>

      @if (error()) { <p class="error">{{ error() }}</p> }
      <div class="row" style="margin-top:12px">
        <button mat-flat-button type="submit" [disabled]="saving()">{{ saving() ? 'Saving…' : 'Save details' }}</button>
        <button mat-button type="button" (click)="cancelled.emit()">Cancel</button>
      </div>
    </form>
  `,
  styles: `
    .fields { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-bottom: 12px; }
    label { display: flex; flex-direction: column; gap: 4px; font-size: .85rem; color: var(--cn-muted); }
    input, select { min-height: 44px; padding: 0 10px; font: inherit; font-size: 1rem; color: var(--cn-ink); border: 1px solid var(--cn-border); border-radius: 10px; background: #fff; min-width: 0; }
    .member-row { display: grid; grid-template-columns: 1fr 120px 80px 48px; gap: 8px; align-items: center; margin-bottom: 8px; }
    @media (max-width: 599px) { .member-row { grid-template-columns: 1fr 1fr; } .member-row .age { grid-column: 1; } }
    .error { color: var(--cn-bad); }
  `,
})
export class PolicyDetailsFormComponent implements OnInit {
  private api = inject(ApiService);

  policy = input.required<PolicyFacts>();
  saved = output<PolicyFacts>();
  cancelled = output<void>();

  readonly relations = ['Self', 'Spouse', 'Father', 'Mother', 'Son', 'Daughter', 'Other'];
  readonly today = new Date().toISOString().slice(0, 10);

  startDate = '';
  sumInsured: number | null = null;
  roomRentPerDay: number | null = null;
  policyNumber = '';
  members = signal<MemberRow[]>([]);
  saving = signal(false);
  error = signal<string | null>(null);

  ngOnInit(): void {
    const p = this.policy();
    this.startDate = p.startDate ?? '';
    this.sumInsured = p.sumInsured || null;
    this.roomRentPerDay = p.roomRent.amount ?? null;
    this.policyNumber = p.policyNumber === 'Not found' ? '' : p.policyNumber;
    this.members.set(p.members.map((m) => ({ name: m.name, relation: m.relation, age: m.age ?? null })));
    if (!this.members().length) this.addMember();
  }

  addMember(): void {
    this.members.update((list) => [...list, { name: '', relation: 'Self', age: null }]);
  }

  removeMember(index: number): void {
    this.members.update((list) => list.filter((_, i) => i !== index));
  }

  save(): void {
    const members: Member[] = this.members()
      .filter((m) => m.name.trim())
      .map((m) => ({ name: m.name.trim(), relation: m.relation, age: m.age ?? null }));
    const details: PolicyDetailsInput = {
      ...(this.startDate ? { startDate: this.startDate } : {}),
      ...(this.sumInsured && this.sumInsured > 0 ? { sumInsured: this.sumInsured } : {}),
      ...(this.roomRentPerDay && this.roomRentPerDay > 0 ? { roomRentPerDay: this.roomRentPerDay } : {}),
      ...(this.policyNumber.trim() ? { policyNumber: this.policyNumber.trim() } : {}),
      ...(members.length ? { members } : {}),
    };
    this.saving.set(true);
    this.error.set(null);
    this.api.savePolicyDetails(details, this.policy()).subscribe({
      next: (facts) => {
        this.saving.set(false);
        this.saved.emit(facts);
      },
      error: (e) => {
        this.saving.set(false);
        this.error.set(e?.error?.detail?.[0]?.msg ?? e?.error?.detail ?? 'Could not save. Please check the values and try again.');
      },
    });
  }
}
