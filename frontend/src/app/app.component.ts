import { ClaimFlowComponent } from './shared/claim-flow.component';
import { VisitorWelcomeComponent } from './shared/visitor-welcome.component';
import { VisitorProfileService } from './services/visitor-profile.service';
import { Component, DestroyRef, HostListener, computed, effect, inject, signal } from '@angular/core';
import { NgTemplateOutlet, ViewportScroller } from '@angular/common';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { catchError, filter, map, of } from 'rxjs';
import { CitationDrawerComponent } from './shared/citation-drawer.component';
import { ChatBarComponent } from './shared/chat-bar.component';
import { CLAIM_TOOLS } from './shared/claim-tools';
import { scrollToSection } from './shared/scroll';
import { TranslatePipe } from './shared/translate.pipe';
import { ApiService, FEATURES, isFullyLive, isLive } from './services/api.service';
import { ChatService } from './services/chat.service';
import { JourneyService } from './services/journey.service';
import { SettingsService } from './services/settings.service';
import { ThemeService } from './services/theme.service';
import { WorkspaceChooserComponent } from './shared/workspace-chooser.component';
import { WorkspaceService } from './services/workspace.service';
import { CitationViewerService } from './services/citation-viewer.service';

interface NavItem {
  path: string;
  label: string;
  /** Label for the phone tab bar, where space is tight. */
  short?: string;
  icon: string;
  exact: boolean;
  /** One line under the label in the menu. */
  desc?: string;
}

const SIZE_LABELS = { sm: '94%', md: '100%', lg: '113%', xl: '125%' } as const;
/** Scroll distance after which the header swaps its text links for the full icon row. */
const SCROLL_REVEAL_PX = 120;

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [ClaimFlowComponent, VisitorWelcomeComponent, WorkspaceChooserComponent, RouterOutlet, RouterLink, RouterLinkActive, NgTemplateOutlet, MatIconModule, CitationDrawerComponent, ChatBarComponent, TranslatePipe],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  readonly profile = inject(VisitorProfileService);
  readonly theme = inject(ThemeService);
  readonly settings = inject(SettingsService);
  readonly journey = inject(JourneyService);
  readonly chat = inject(ChatService);
  readonly workspace = inject(WorkspaceService);
  private translate = new TranslatePipe();
  readonly live = isFullyLive();
  readonly sessionInfo = toSignal(inject(ApiService).getSessionInfo().pipe(catchError(() => of(null))));
  readonly liveDemo = computed(() => this.live && this.sessionInfo()?.mode === 'live_demo');
  readonly partlyLive = !this.live && FEATURES.some((f) => isLive(f.id));
  readonly menuOpen = signal(false);
  readonly scrolled = signal(false);

  readonly path = toSignal(
    inject(Router).events.pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd), map((e) => e.urlAfterRedirects.split(/[?#]/)[0])),
    { initialValue: '/' },
  );
  readonly onClaimSubpage = computed(() => this.path() === '/case/detail' || CLAIM_TOOLS.some((n) => n.path === this.path()));
  readonly onAskPage = computed(() => this.path() === '/ask');
  readonly onHome = computed(() => this.path() === '/');
  /** Claim progress belongs to the claim workspace, never the public landing page. */
  readonly showProgress = computed(() => !!this.journey.claimCase()?.documents.length && (this.path() === '/case' || (this.onClaimSubpage() && this.path() !== '/upload')));
  /** Home › Section › Page, for the slim banner on inner pages. */
  readonly crumbs = computed<{ label: string; path: string; icon: string }[]>(() => {
    const p = this.path();
    if (p === '/dashboard' || (p === '/ask' && this.workspace.mode() === 'general')) return [];
    const home = { label: 'Dashboard', path: '/dashboard', icon: 'dashboard' };
    const main = this.mainNav.find((n) => n.path === p && p !== '/');
    if (main) return [home, { label: main.label, path: p, icon: main.icon }];
    if (p === '/case/detail') return [home, { label: 'My claims', path: '/case', icon: 'folder_shared' }, { label: 'Claim details', path: p, icon: 'folder_open' }];
    const sub = CLAIM_TOOLS.find((n) => n.path === p);
    if (sub) return [home, { label: 'My claim', path: '/case', icon: 'folder_shared' }, { label: sub.label, path: p, icon: sub.icon }];
    if (p === '/status') return [home, { label: 'Demo and live settings', path: p, icon: 'tune' }];
    return [];
  });
  readonly sizeLabel = computed(() => SIZE_LABELS[this.settings.textSize()]);
  readonly journeyLabel = computed(() => {
    this.settings.lang();
    const t = (s: string) => this.translate.transform(s);
    const current = this.journey.current();
    if (!current) return t('All done');
    return `${this.journey.doneCount()} ${t('of')} ${this.journey.steps().length} ${t('steps done')} · ${t('Next')}: ${t(current.todo)}`;
  });
  /** The header chip is narrow at laptop widths, so it shows "4/8 · next step" (steps done, as everywhere else). */
  readonly journeyShort = computed(() => {
    this.settings.lang();
    const current = this.journey.current();
    if (!current) return this.translate.transform('All done');
    return `${this.journey.doneCount()}/${this.journey.steps().length} · ${this.translate.transform(current.todo)}`;
  });

  constructor() {
    const citations = inject(CitationViewerService);
    effect(() => { this.workspace.mode(); citations.close(); });
    // Router jumps to #section must clear the sticky header (and on phones the chat bar docked under it).
    inject(ViewportScroller).setOffset(() => {
      const header = document.querySelector('.topbar')?.getBoundingClientRect().bottom ?? 64;
      const dock = innerWidth < 900 ? document.querySelector('app-chat-bar .dock')?.getBoundingClientRect().bottom ?? 0 : 0;
      return [0, Math.max(header, dock) + 12];
    });
    // Links with #section (dashboard, search) scroll there once the page's data has rendered.
    inject(Router).events.pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd), takeUntilDestroyed(inject(DestroyRef)))
      .subscribe((e) => {
        this.menuOpen.set(false);
        const fragment = e.urlAfterRedirects.split('#')[1];
        if (fragment) scrollToSection(decodeURIComponent(fragment));
      });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.menuOpen.set(false);
  }

  @HostListener('window:scroll')
  onScroll(): void {
    const past = scrollY > SCROLL_REVEAL_PX;
    if (past !== this.scrolled()) this.scrolled.set(past);
  }

  openHelper(): void { this.chat.openPanel(); }

  /** Centre tab on phones: opens or closes the chat (the Ask page already shows it). */
  toggleAsk(): void {
    this.menuOpen.set(false);
    if (this.onAskPage()) return;
    if (this.chat.panelOpen()) this.chat.closePanel();
    else this.chat.openPanel();
  }

  readonly mainNav: NavItem[] = [
    { path: '/', label: 'Welcome', short: 'Welcome', icon: 'home', exact: true, desc: 'General insurance guidance from Nessi' },
    { path: '/dashboard', label: 'Dashboard', short: 'Home', icon: 'dashboard', exact: true, desc: "Your fictional example workspace" },
    { path: '/policy', label: 'My policy', short: 'Policy', icon: 'policy', exact: true, desc: 'Cover, limits, waiting times' },
    { path: '/case', label: 'My claims', short: 'Claims', icon: 'folder_shared', exact: false, desc: 'Papers, diary, your files' },
    { path: '/ask', label: 'Chat', icon: 'forum', exact: true, desc: 'Answers from your own papers' },
  ];
  /** Phone tab bar: Home, Policy | centre Ask | Claim, More. */
  readonly tabsLeft = this.mainNav.filter((n) => ['/dashboard', '/policy'].includes(n.path));
  readonly tabsRight = this.mainNav.filter((n) => n.path === '/case');
  /** The menu only lists pages that aren't already in the header or the phone tab bar. */
  readonly menuPages = CLAIM_TOOLS;
}
