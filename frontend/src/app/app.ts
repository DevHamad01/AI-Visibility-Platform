import { HttpClient } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { catchError, of, startWith, switchMap, timer } from 'rxjs';
import { environment } from '../environments/environment';
import { ThemeService } from './core/theme.service';
import { Icon, IconName } from './shared/icon';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
  templateUrl: './app.html',
})
export class App {
  readonly theme = inject(ThemeService);
  private readonly http = inject(HttpClient);
  private readonly destroy = inject(DestroyRef);

  readonly navOpen = signal(false);

  /**
   * null until the first probe answers, so the indicator never claims the API
   * is down during startup.
   */
  readonly apiReady = signal<boolean | null>(null);

  /** Swagger is served by the API, whose origin differs from the app in dev. */
  readonly docsUrl = new URL('/api/docs/swagger', apiOrigin()).toString();

  readonly nav: { path: string; label: string; icon: IconName; exact: boolean }[] = [
    { path: '/', label: 'Overview', icon: 'grid', exact: true },
    { path: '/brands/new', label: 'Add brand', icon: 'plus', exact: false },
  ];

  constructor() {
    // /readyz checks DB, Redis and config, so this reflects whether a run
    // could actually start — not just whether nginx is up.
    timer(0, 30_000)
      .pipe(
        startWith(0),
        switchMap(() =>
          this.http
            .get(new URL('/readyz', apiOrigin()).toString(), { observe: 'response' })
            .pipe(catchError(() => of(null))),
        ),
        takeUntilDestroyed(this.destroy),
      )
      .subscribe((response) => this.apiReady.set(response?.ok === true));
  }
}

function apiOrigin(): string {
  try {
    return new URL(environment.apiUrl, location.origin).origin;
  } catch {
    return location.origin;
  }
}
