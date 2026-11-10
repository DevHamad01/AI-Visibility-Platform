import { Injectable, signal } from '@angular/core';
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly dark = signal(this.initial());
  constructor() {
    this.apply();
  }
  toggle() {
    this.dark.update((value) => !value);
    this.apply();
    try {
      localStorage.setItem('signal-theme', this.dark() ? 'dark' : 'light');
    } catch {
      /* Storage is optional. */
    }
  }
  private initial() {
    try {
      return localStorage.getItem('signal-theme')
        ? localStorage.getItem('signal-theme') === 'dark'
        : matchMedia('(prefers-color-scheme: dark)').matches;
    } catch {
      return false;
    }
  }
  private apply() {
    document.documentElement.dataset['theme'] = this.dark() ? 'dark' : 'light';
  }
}
