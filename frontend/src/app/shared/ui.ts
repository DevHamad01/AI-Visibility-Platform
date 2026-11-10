import { Component, computed, input, output } from '@angular/core';
import { Problem } from '../core/models';
import { Icon, IconName } from './icon';

/** Status vocabulary shared by runs, stages and recommendations. */
type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger';

const STATUS_TONE: Record<string, { tone: Tone; icon: IconName; label?: string }> = {
  // run
  queued: { tone: 'neutral', icon: 'clock' },
  running: { tone: 'brand', icon: 'spinner' },
  succeeded: { tone: 'success', icon: 'check-circle' },
  partial: { tone: 'warning', icon: 'alert-triangle' },
  failed: { tone: 'danger', icon: 'alert-circle' },
  // stage
  pending: { tone: 'neutral', icon: 'clock' },
  skipped: { tone: 'neutral', icon: 'minus' },
  // recommendation
  todo: { tone: 'neutral', icon: 'target', label: 'To do' },
  in_progress: { tone: 'brand', icon: 'play', label: 'In progress' },
  done: { tone: 'success', icon: 'check', label: 'Done' },
  dismissed: { tone: 'neutral', icon: 'x', label: 'Dismissed' },
};

@Component({
  selector: 'app-status-badge',
  imports: [Icon],
  template: `<span [class]="cls()">
    <app-icon [name]="meta().icon" [size]="12" />
    {{ text() }}
  </span>`,
})
export class StatusBadge {
  readonly status = input.required<string>();
  readonly label = input('');

  protected readonly meta = computed(
    () => STATUS_TONE[this.status()] ?? { tone: 'neutral' as Tone, icon: 'info' as IconName },
  );
  protected readonly text = computed(
    () => this.label() || this.meta().label || this.status().replaceAll('_', ' '),
  );
  protected readonly cls = computed(() => `badge-${this.meta().tone}`);
}

/** KPI tile. The figure is the loudest thing in the tile; the label never competes. */
@Component({
  selector: 'app-stat',
  imports: [Icon],
  template: `<div class="flex flex-col gap-1.5">
    <span class="eyebrow">{{ label() }}</span>
    <span class="tnum text-display-sm font-semibold text-ink-950">{{ value() }}</span>
    @if (detail() || delta() !== null) {
      <span class="flex items-center gap-1.5 text-label-xs text-ink-400">
        @if (delta() !== null) {
          <span [class]="deltaCls()">
            <app-icon [name]="deltaIcon()" [size]="12" />
            {{ deltaText() }}
          </span>
        }
        {{ detail() }}
      </span>
    }
  </div>`,
})
export class Stat {
  readonly label = input.required<string>();
  readonly value = input.required<string | number>();
  readonly detail = input('');
  /** Signed change; `null` hides the delta pill entirely. */
  readonly delta = input<number | null>(null);
  /** When true a *negative* delta is the good outcome (e.g. gap closing). */
  readonly invertDelta = input(false);

  private readonly good = computed(() => {
    const d = this.delta() ?? 0;
    return this.invertDelta() ? d < 0 : d > 0;
  });
  protected readonly deltaIcon = computed<IconName>(() =>
    (this.delta() ?? 0) === 0 ? 'minus' : (this.delta() ?? 0) > 0 ? 'trending-up' : 'trending-down',
  );
  protected readonly deltaText = computed(() => {
    const d = this.delta() ?? 0;
    return `${d > 0 ? '+' : ''}${Number(d.toFixed(1))}`;
  });
  protected readonly deltaCls = computed(() =>
    (this.delta() ?? 0) === 0 ? 'badge-neutral' : this.good() ? 'badge-success' : 'badge-danger',
  );
}

/** Loading skeleton. Mirrors the shape of what is coming, not a generic spinner. */
@Component({
  selector: 'app-skeleton',
  template: `@switch (variant()) {
    @case ('stats') {
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true" aria-label="Loading">
        @for (i of rows(); track i) {
          <div class="card p-4">
            <div class="skeleton h-3 w-20"></div>
            <div class="skeleton mt-3 h-7 w-24"></div>
          </div>
        }
      </div>
    }
    @case ('table') {
      <div class="card overflow-hidden" aria-busy="true" aria-label="Loading">
        <div class="border-b-hairline border-stroke-200 bg-surface-50 px-3 py-2.5">
          <div class="skeleton h-3 w-32"></div>
        </div>
        @for (i of rows(); track i) {
          <div
            class="flex items-center gap-4 border-b-hairline border-stroke-200 px-3 py-3 last:border-b-0"
          >
            <div class="skeleton h-3.5 flex-1"></div>
            <div class="skeleton h-3.5 w-16"></div>
            <div class="skeleton h-3.5 w-10"></div>
          </div>
        }
      </div>
    }
    @default {
      <div class="card space-y-3 p-4" aria-busy="true" aria-label="Loading">
        <div class="skeleton h-4 w-40"></div>
        <div class="skeleton h-3 w-full"></div>
        <div class="skeleton h-3 w-5/6"></div>
      </div>
    }
  }`,
})
export class Skeleton {
  readonly variant = input<'card' | 'stats' | 'table'>('card');
  readonly count = input(4);
  protected readonly rows = computed(() => Array.from({ length: this.count() }, (_, i) => i));
}

/** Empty state. Always names the next action — never a dead end. */
@Component({
  selector: 'app-empty',
  imports: [Icon],
  template: `<div class="flex flex-col items-center justify-center px-6 py-10 text-center">
    <span
      class="mb-3.5 grid h-11 w-11 place-items-center rounded-12 border-hairline border-stroke-200 bg-surface-50 text-ink-400"
    >
      <app-icon [name]="icon()" [size]="20" />
    </span>
    <h3 class="text-label-md font-semibold text-ink-950">{{ title() }}</h3>
    @if (text()) {
      <p class="mt-1.5 max-w-sm text-label-sm text-ink-600">{{ text() }}</p>
    }
    <!-- empty:hidden so an empty state with no CTA does not reserve the
         action row's height — three stacked empties get tall fast. -->
    <div class="mt-5 flex flex-wrap items-center justify-center gap-2 empty:mt-0 empty:hidden">
      <ng-content />
    </div>
  </div>`,
})
export class Empty {
  readonly title = input('Nothing here yet');
  readonly text = input('');
  readonly icon = input<IconName>('layers');
}

/** Error state. Friendly sentence, the trace id to quote, and a retry. */
@Component({
  selector: 'app-error',
  imports: [Icon],
  template: `<div
    class="card border-danger-500/30 p-4"
    role="alert"
    style="background: rgb(var(--danger-500) / 0.04)"
  >
    <div class="flex gap-3">
      <span class="mt-0.5 text-danger-700"><app-icon name="alert-circle" [size]="18" /></span>
      <div class="min-w-0 flex-1">
        <h3 class="text-label-sm font-semibold text-ink-950">
          {{ problem().title || 'Something went wrong' }}
        </h3>
        @if (problem().detail) {
          <p class="mt-1 text-label-sm text-ink-600">{{ problem().detail }}</p>
        }
        @if (problem().errors?.length) {
          <ul class="mt-2 space-y-1">
            @for (e of problem().errors; track $index) {
              <li class="text-label-xs text-ink-600">
                <span class="font-medium text-ink-700">{{ (e.loc || []).join('.') }}</span>
                {{ e.msg }}
              </li>
            }
          </ul>
        }
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" class="btn-secondary btn-sm" (click)="retry.emit()">
            <app-icon name="refresh" [size]="12" /> Try again
          </button>
          @if (problem().trace_id) {
            <span class="tnum text-label-xs text-ink-400">
              Trace <span class="font-medium text-ink-600">{{ problem().trace_id }}</span>
            </span>
          }
        </div>
      </div>
    </div>
  </div>`,
})
export class ErrorState {
  readonly problem = input.required<Problem>();
  readonly retry = output<void>();
}

/**
 * Partial-failure banner: says which stages failed, in plain language, and
 * what is therefore missing from the numbers on screen.
 */
@Component({
  selector: 'app-partial-banner',
  imports: [Icon],
  template: `<div
    class="card border-warning-500/30 p-4"
    role="status"
    style="background: rgb(var(--warning-500) / 0.05)"
  >
    <div class="flex gap-3">
      <span class="mt-0.5 text-warning-700"><app-icon name="alert-triangle" [size]="18" /></span>
      <div class="min-w-0 flex-1">
        <h3 class="text-label-sm font-semibold text-ink-950">{{ title() }}</h3>
        <p class="mt-1 text-label-sm text-ink-600">{{ text() }}</p>
        @if (stages().length) {
          <ul class="mt-2.5 space-y-1.5">
            @for (s of stages(); track s.stage) {
              <li class="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-label-xs">
                <span class="badge-warning">{{ s.stage.replaceAll('_', ' ') }}</span>
                <span class="text-ink-600">{{ s.reason }}</span>
              </li>
            }
          </ul>
        }
        <ng-content />
      </div>
    </div>
  </div>`,
})
export class PartialBanner {
  readonly title = input('Some data is missing from this run');
  readonly text = input(
    'The stages below failed, so the scores on this page were computed from the data that did arrive.',
  );
  readonly stages = input<{ stage: string; reason: string }[]>([]);
}

/** Page header: one h1, optional back link, actions on the right. */
@Component({
  selector: 'app-page-header',
  template: `<header class="mb-6 flex flex-wrap items-end justify-between gap-4">
    <div class="min-w-0">
      @if (eyebrow()) {
        <p class="eyebrow mb-1.5">{{ eyebrow() }}</p>
      }
      <h1 class="truncate text-display-md font-semibold text-ink-950">{{ title() }}</h1>
      @if (subtitle()) {
        <p class="mt-1.5 max-w-2xl text-label-sm text-ink-600">{{ subtitle() }}</p>
      }
    </div>
    <div class="flex flex-wrap items-center gap-2"><ng-content /></div>
  </header>`,
})
export class PageHeader {
  readonly title = input.required<string>();
  readonly subtitle = input('');
  readonly eyebrow = input('');
}

/** Section card with a titled header bar and optional toolbar slot. */
@Component({
  selector: 'app-section',
  template: `<section class="card overflow-hidden">
    <div
      class="flex flex-wrap items-center justify-between gap-3 border-b-hairline border-stroke-200 px-4 py-3"
    >
      <div class="min-w-0">
        <h2 class="panel-title truncate">{{ title() }}</h2>
        @if (subtitle()) {
          <p class="mt-0.5 text-label-xs text-ink-400">{{ subtitle() }}</p>
        }
      </div>
      <div class="flex flex-wrap items-center gap-2"><ng-content select="[toolbar]" /></div>
    </div>
    <ng-content />
  </section>`,
})
export class Section {
  readonly title = input.required<string>();
  readonly subtitle = input('');
}

/**
 * Horizontal score meter, 0–100. The fill is the sequential coral ramp, so a
 * high-opportunity row reads loud without needing a second colour legend.
 */
@Component({
  selector: 'app-score-meter',
  template: `<span class="flex items-center gap-2">
    <span class="tnum w-9 text-right text-label-sm font-semibold text-ink-950">{{
      display()
    }}</span>
    <span
      class="relative h-1.5 w-full min-w-10 overflow-hidden rounded-full bg-surface-200"
      role="img"
      [attr.aria-label]="'Opportunity score ' + display() + ' of 100'"
    >
      <span
        class="absolute inset-y-0 left-0 rounded-full transition-[width] duration-150"
        [style.width.%]="pct()"
        [style.background]="fill()"
      ></span>
    </span>
  </span>`,
})
export class ScoreMeter {
  readonly score = input.required<number>();

  protected readonly pct = computed(() => Math.max(2, Math.min(100, this.score())));
  protected readonly display = computed(() => this.score().toFixed(1));
  /** Opacity carries magnitude on top of width, so low rows recede. */
  protected readonly fill = computed(
    () => `rgb(var(--brand-500) / ${(0.45 + (this.pct() / 100) * 0.55).toFixed(2)})`,
  );
}
