import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { problemOf } from '../core/errors';
import { BrandOverview, Problem } from '../core/models';
import { Icon } from '../shared/icon';
import {
  Empty,
  ErrorState,
  PageHeader,
  ScoreMeter,
  Section,
  Skeleton,
  Stat,
  StatusBadge,
} from '../shared/ui';

@Component({
  imports: [
    RouterLink,
    DatePipe,
    DecimalPipe,
    Icon,
    Empty,
    ErrorState,
    PageHeader,
    ScoreMeter,
    Section,
    Skeleton,
    Stat,
    StatusBadge,
  ],
  template: `<app-page-header
      eyebrow="Portfolio"
      title="Visibility overview"
      subtitle="Where each brand shows up across Google, AI Overviews and LLM answers — and the gaps worth closing first."
    >
      <a routerLink="/brands/new" class="btn-primary">
        <app-icon name="plus" [size]="14" /> Add brand
      </a>
    </app-page-header>

    @if (loading()) {
      <app-skeleton variant="stats" />
      <div class="mt-6"><app-skeleton variant="table" [count]="3" /></div>
    } @else if (error(); as problem) {
      <app-error [problem]="problem" (retry)="load()" />
    } @else {
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="card p-4">
          <app-stat label="Tracked brands" [value]="brands().length" detail="in this workspace" />
        </div>
        <div class="card p-4">
          <app-stat label="Open opportunities" [value]="opportunities()" detail="latest run each" />
        </div>
        <div class="card p-4">
          <app-stat label="Clean analyses" [value]="completed()" detail="finished without gaps" />
        </div>
        <div class="card p-4">
          <app-stat label="Need attention" [value]="attention()" detail="partial or failed runs" />
        </div>
      </div>

      <div class="mt-6">
        @if (!brands().length) {
          <div class="card">
            <app-empty
              icon="building"
              title="Track your first brand"
              text="Add a brand with its domain and two or three competitors. Signal then measures where you appear versus them, and scores the gaps."
            >
              <a routerLink="/brands/new" class="btn-primary">
                <app-icon name="plus" [size]="14" /> Add your first brand
              </a>
            </app-empty>
          </div>
        } @else {
          <app-section
            title="Brands"
            [subtitle]="brands().length + ' tracked · highest remaining gap first'"
          >
            <ul class="divide-y-hairline divide-stroke-200">
              @for (brand of ranked(); track brand.brand_id) {
                <li>
                  <a
                    [routerLink]="['/brands', brand.brand_id]"
                    class="group flex flex-wrap items-center gap-4 px-4 py-3.5 transition-colors duration-150 hover:bg-surface-50"
                  >
                    <span
                      class="grid h-9 w-9 shrink-0 place-items-center rounded-8 border-hairline border-stroke-200 bg-surface-50 text-label-sm font-semibold text-ink-700"
                    >
                      {{ brand.brand_name.charAt(0).toUpperCase() }}
                    </span>

                    <span class="min-w-[180px] flex-1">
                      <span class="block truncate text-label-sm font-semibold text-ink-950">
                        {{ brand.brand_name }}
                      </span>
                      <span class="mt-0.5 block text-label-xs text-ink-400">
                        {{
                          brand.latest_run_finished_at
                            ? 'Measured ' + (brand.latest_run_finished_at | date: 'MMM d, HH:mm')
                            : 'Not measured yet'
                        }}
                      </span>
                    </span>

                    <span class="w-[150px] shrink-0">
                      <span class="eyebrow block">Top gap</span>
                      @if (brand.top_score === null) {
                        <span class="mt-1 block text-label-sm text-ink-400">—</span>
                      } @else {
                        <span class="mt-1 block"
                          ><app-score-meter [score]="brand.top_score"
                        /></span>
                      }
                    </span>

                    <span class="w-[110px] shrink-0">
                      <span class="eyebrow block">Opportunities</span>
                      <span class="tnum mt-1 block text-label-sm font-semibold text-ink-950">
                        {{ brand.opportunity_count | number }}
                      </span>
                    </span>

                    <!-- Fixed width: the badge label varies ("failed" vs
                         "Not measured"), and without it every column to the
                         left shifts row by row. -->
                    <span class="flex w-[164px] shrink-0 items-center justify-end gap-3">
                      <app-status-badge
                        [status]="brand.latest_run_status || 'pending'"
                        [label]="brand.latest_run_status ? '' : 'Not measured'"
                      />
                      <span
                        class="text-ink-400 transition-colors duration-150 group-hover:text-brand-500"
                      >
                        <app-icon name="chevron-right" [size]="16" />
                      </span>
                    </span>
                  </a>
                </li>
              }
            </ul>
          </app-section>

          <p class="mt-3 flex items-start gap-2 px-1 text-label-xs leading-[16px] text-ink-400">
            <app-icon name="info" [size]="12" />
            <span>
              A higher score means a
              <strong class="font-medium text-ink-600">bigger remaining gap</strong> — high demand
              where you are not visible but competitors are. Scores are computed in Python from
              DataForSEO data, never by the model.
            </span>
          </p>
        }
      </div>
    }`,
})
export class OverviewPage {
  private readonly api = inject(ApiService);

  readonly loading = signal(true);
  readonly error = signal<Problem | null>(null);
  readonly brands = signal<BrandOverview[]>([]);

  /** Biggest unclosed gap first; unmeasured brands sink to the bottom. */
  readonly ranked = computed(() =>
    [...this.brands()].sort((a, b) => (b.top_score ?? -1) - (a.top_score ?? -1)),
  );
  readonly opportunities = computed(() =>
    this.brands().reduce((sum, b) => sum + b.opportunity_count, 0),
  );
  readonly completed = computed(
    () => this.brands().filter((b) => b.latest_run_status === 'succeeded').length,
  );
  readonly attention = computed(
    () =>
      this.brands().filter((b) => ['partial', 'failed'].includes(b.latest_run_status ?? '')).length,
  );

  constructor() {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.api.overview().subscribe({
      next: (result) => {
        this.brands.set(result.brands);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(problemOf(e));
        this.loading.set(false);
      },
    });
  }
}
