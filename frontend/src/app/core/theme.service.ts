import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'signal-theme';

/**
 * Theme state. Writes the `dark` class on <html> (what Tailwind's `dark:`
 * variant and our CSS custom properties key off) plus a `data-theme`
 * attribute, which the ECharts theme reads so charts re-skin with the UI.
 */
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
      localStorage.setItem(STORAGE_KEY, this.dark() ? 'dark' : 'light');
    } catch {
      /* Storage is optional — the theme still applies for this session. */
    }
  }

  private initial() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return stored === 'dark';
      return matchMedia('(prefers-color-scheme: dark)').matches;
    } catch {
      return false;
    }
  }

  private apply() {
    const root = document.documentElement;
    root.classList.toggle('dark', this.dark());
    root.dataset['theme'] = this.dark() ? 'dark' : 'light';
  }
}
