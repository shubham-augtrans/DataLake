import { Injectable, signal } from '@angular/core';

export type AppTheme = 'dark' | 'light';

const STORAGE_KEY = 'theme';
const THEME_LINK_ID = 'app-theme';
const THEME_FOLDER: Record<AppTheme, string> = {
  dark: 'aura-dark-indigo',
  light: 'aura-light-blue',
};

@Injectable({
  providedIn: 'root',
})
export class ThemeService {

  // index.html's inline script already set the initial <html data-theme>
  // and PrimeNG <link> before Angular booted (avoids a flash of the wrong
  // theme) - this signal just picks up whatever it decided, so the header
  // toggle's icon starts in sync with what's actually on screen.
  readonly theme = signal<AppTheme>(this.readInitialTheme());

  private readInitialTheme(): AppTheme {
    const attr = document.documentElement.getAttribute('data-theme');
    return attr === 'light' ? 'light' : 'dark';
  }

  toggle(): void {
    this.setTheme(this.theme() === 'dark' ? 'light' : 'dark');
  }

  setTheme(theme: AppTheme): void {
    this.theme.set(theme);
    document.documentElement.setAttribute('data-theme', theme);

    const link = document.getElementById(THEME_LINK_ID) as HTMLLinkElement | null;
    if (link) {
      link.href = `assets/themes/${THEME_FOLDER[theme]}/theme.css`;
    }

    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Private-browsing/storage-blocked - theme still applies for this
      // page load, it just won't persist across reloads.
    }
  }
}
