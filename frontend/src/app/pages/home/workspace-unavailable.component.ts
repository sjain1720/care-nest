import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true, imports: [RouterLink],
  template: `<section class="page"><div class="card"><h1>The dashboard is temporarily unavailable</h1>
    <p>Please try again shortly. You can still ask Nessi general insurance questions on the welcome page.</p>
    <a routerLink="/dashboard">Try dashboard again</a> · <a routerLink="/">Ask Nessi</a></div></section>`,
})
export class WorkspaceUnavailableComponent {}
