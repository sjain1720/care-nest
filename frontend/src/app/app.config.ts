import { firstValueFrom, catchError, of, timeout } from 'rxjs';
import { ApplicationConfig, inject, provideAppInitializer, provideZoneChangeDetection } from '@angular/core';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling, withViewTransitions } from '@angular/router';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { routes } from './app.routes';
import { errorInterceptor } from './services/error.interceptor';
import { workspaceInterceptor } from './services/workspace.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideHttpClient(withInterceptors([workspaceInterceptor, errorInterceptor])),
    // Establish the guest cookie before parallel page requests can create different sessions.
    provideAppInitializer(() => firstValueFrom(inject(HttpClient).get('/api/health').pipe(timeout(5000), catchError(() => of(null))))),
    provideRouter(routes, withComponentInputBinding(), withInMemoryScrolling({ scrollPositionRestoration: 'top', anchorScrolling: 'enabled' }),
      withViewTransitions({
        skipInitialTransition: true,
        onViewTransitionCreated: ({ transition }) => {
          // A hidden tab or a quick second click aborts the animation; the page still changes, so ignore it.
          transition.ready.catch(() => undefined);
          transition.finished.catch(() => undefined);
          if (matchMedia('(prefers-reduced-motion: reduce)').matches) transition.skipTransition();
        },
      })),
    provideAnimationsAsync(),
  ],
};
