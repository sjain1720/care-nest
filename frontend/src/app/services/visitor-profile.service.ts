import { VisitorProfile } from '../models/models';
import { Injectable, signal } from '@angular/core';

/** Bootstrap the root cookie before document APIs; a display name is not an account. */
@Injectable({providedIn: 'root'})
export class VisitorProfileService {
  readonly name = signal('');
  readonly loaded = signal(false);
  readonly error = signal('');
  private pending?: Promise<void>;
  load(): Promise<void> {
    if (this.loaded()) return Promise.resolve();
    if (!this.pending) this.pending = this.read().finally(() => { this.pending = undefined; });
    return this.pending;
  }
  private async read(): Promise<void> {
    try {
      const response = await fetch('/api/session/profile?workspace=general', {credentials:'same-origin', signal:AbortSignal.timeout(20000)});
      if (!response.ok) throw Error();
      const data: VisitorProfile = await response.json(); this.name.set(data.displayName || ''); this.loaded.set(true); this.error.set('');
    } catch { this.error.set('We could not open your guest session. Please retry.'); throw Error('Guest session unavailable'); }
  }
  async save(name: string): Promise<void> {
    await this.load();
    const response = await fetch('/api/session/profile?workspace=general', {method:'PUT', credentials:'same-origin', signal:AbortSignal.timeout(20000), headers:{'Content-Type':'application/json'}, body:JSON.stringify({displayName:name.trim()})});
    if (!response.ok) throw Error('Could not save your name. Please use 1–60 characters and retry.');
    this.name.set((await response.json()).displayName);
  }
}
