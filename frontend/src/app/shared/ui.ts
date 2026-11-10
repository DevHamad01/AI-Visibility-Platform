import { Component, input, output } from '@angular/core';
import { Problem } from '../core/models';
@Component({
  selector: 'app-badge',
  template: `<span class="badge" [attr.data-status]="status()"
    ><span class="status-dot"></span>{{ label() || status().replaceAll('_', ' ') }}</span
  >`,
})
export class Badge {
  status = input('pending');
  label = input('');
}
@Component({
  selector: 'app-loading',
  template: `<div class="skeleton-group" aria-busy="true" aria-label="Loading">
    <div class="skeleton skeleton-title"></div>
    <div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-card"></div>
  </div>`,
})
export class Loading {}
@Component({
  selector: 'app-empty',
  template: `<div class="empty-state">
    <span class="empty-icon" aria-hidden="true">◇</span>
    <h3>{{ title() }}</h3>
    <p>{{ text() }}</p>
    <ng-content />
  </div>`,
})
export class Empty {
  title = input('Nothing here yet');
  text = input('');
}
@Component({
  selector: 'app-error',
  template: `<div class="notice danger" role="alert">
    <strong>{{ problem().title || 'Something went wrong' }}</strong>
    <p>{{ problem().detail }}</p>
    @if (problem().trace_id) {
      <p class="mono">Trace: {{ problem().trace_id }}</p>
    }
    <button class="btn small" (click)="retry.emit()">Try again</button>
  </div>`,
})
export class ErrorState {
  problem = input.required<Problem>();
  retry = output<void>();
}
@Component({
  selector: 'app-stat',
  template: `<div class="stat">
    <span class="eyebrow">{{ label() }}</span
    ><strong>{{ value() }}</strong
    ><span class="muted small-text">{{ detail() }}</span>
  </div>`,
})
export class Stat {
  label = input.required<string>();
  value = input.required<string | number>();
  detail = input('');
}
