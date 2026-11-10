import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { describe, expect, it } from 'vitest';
describe('Workspace shell', () => {
  it('provides navigation and a keyboard skip link', async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('nav')?.getAttribute('aria-label')).toBe('Main navigation');
    expect(el.querySelector('.skip-link')?.getAttribute('href')).toBe('#main');
  });
});
