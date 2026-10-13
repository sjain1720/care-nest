import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Observable, tap } from 'rxjs';
import { ApiService } from './api.service';
import { JourneyService } from './journey.service';
import { SettingsService } from './settings.service';
import { ClaimCase, TimelineEventInput } from '../models/models';
import { DECISION_DAYS, REPLY_DAYS } from '../shared/claim-diary';

function message(input: TimelineEventInput, hi: boolean): string {
  switch (input.kind) {
    case 'claim_sent':
      return hi ? `क्लेम भेजा गया ✓ – ${DECISION_DAYS} दिन में फ़ैसला न आए तो हम बताएँगे।` : `Claim marked as sent ✓ – we'll tell you if there's no decision in ${DECISION_DAYS} days.`;
    case 'letter_sent':
      return hi ? `भेजा गया ✓ – ${REPLY_DAYS} दिन में जवाब न आए तो हम याद दिलाएँगे।` : `Marked as sent ✓ – we'll remind you if there's no reply in ${REPLY_DAYS} days.`;
    case 'complaint_filed':
      return (input.level ?? 1) === 1
        ? (hi ? `शिकायत दर्ज ✓ – ${REPLY_DAYS} दिन में जवाब न आए तो हम याद दिलाएँगे।` : `Complaint saved ✓ – we'll remind you if there's no reply in ${REPLY_DAYS} days.`)
        : (hi ? 'शिकायत क्लेम डायरी में सेव ✓' : 'Complaint saved to your claim diary ✓');
    case 'closed':
      return hi ? 'क्लेम बंद ✓' : 'Claim closed ✓';
    default:
      return hi ? 'क्लेम डायरी में सेव ✓' : 'Saved to your claim diary ✓';
  }
}

/** Adds a claim-diary entry and confirms it with a short message that has an Undo button. */
@Injectable({ providedIn: 'root' })
export class DiaryActionsService {
  private api = inject(ApiService);
  private journey = inject(JourneyService);
  private snackBar = inject(MatSnackBar);
  private settings = inject(SettingsService);

  add(input: TimelineEventInput): Observable<ClaimCase | null> {
    const before = new Set(this.journey.timeline().map((e) => e.id));
    const hi = this.settings.lang() === 'hi';
    return this.api.addTimelineEvent(input).pipe(
      tap((c) => {
        const added = (c?.timeline ?? []).find((e) => !before.has(e.id));
        const ref = this.snackBar.open(message(input, hi), added ? (hi ? 'वापस लें' : 'Undo') : undefined, { duration: 7000 });
        if (added) {
          ref.onAction().subscribe(() =>
            this.api.removeTimelineEvent(added.id).subscribe(() => this.snackBar.open(hi ? 'वापस ले लिया' : 'Undone', undefined, { duration: 2500 })));
        }
      }),
    );
  }
}
