import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { CitationDrawerComponent } from './shared/citation-drawer.component';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  exact: boolean;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatIconModule, CitationDrawerComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  readonly mainNav: NavItem[] = [
    { path: '/', label: 'Home', icon: 'home', exact: true },
    { path: '/policy', label: 'My policy', icon: 'policy', exact: true },
    { path: '/case', label: 'My case', icon: 'folder_shared', exact: false },
    { path: '/ask', label: 'Ask', icon: 'forum', exact: true },
  ];

  readonly caseNav: NavItem[] = [
    { path: '/case/query', label: 'Insurer query helper', icon: 'quiz', exact: true },
    { path: '/case/bill', label: 'Bill check', icon: 'receipt_long', exact: true },
    { path: '/case/settlement', label: 'Settlement breakdown', icon: 'stacked_bar_chart', exact: true },
    { path: '/case/letter', label: 'Letter to insurer', icon: 'edit_note', exact: true },
    { path: '/upload', label: 'Upload documents', icon: 'upload_file', exact: true },
  ];
}
