import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { BrandOverview, Problem } from '../core/models';
import { problemOf } from '../core/errors';
import { Badge, Empty, ErrorState, Loading, Stat } from '../shared/ui';
@Component({
  imports: [RouterLink, DatePipe, DecimalPipe, Badge, Empty, ErrorState, Loading, Stat],
  template: ` <div class="page-head">
      <div>
        <span class="eyebrow">Your visibility, in focus</span>
        <h1>Portfolio overview</h1>
        <p>Understand where your brands appear. Find the gaps worth closing.</p>
      </div>
      <a class="btn primary" routerLink="/brands/new">＋ Add a brand</a>
    </div>
    @if (loading()) {
      <app-loading />
    } @else if (error(); as p) {
      <app-error [problem]="p" (retry)="load()" />
    } @else {
      <div class="stats">
        <app-stat
          label="Tracked brands"
          [value]="brands().length"
          detail="Your connected portfolio"
        /><app-stat
          label="Opportunities"
          [value]="opportunities()"
          detail="Across latest analyses"
        /><app-stat
          label="Completed analyses"
          [value]="completed()"
          detail="Latest run per brand"
        /><app-stat
          label="Need attention"
          [value]="attention()"
          detail="Failed or partial analyses"
        />
      </div>
      <div class="section-head">
        <div>
          <h2>Your brands</h2>
          <p>A clear view of every brand you track.</p>
        </div>
        <span class="eyebrow">{{ brands().length }} brands</span>
      </div>
      @if (!brands().length) {
        <app-empty
          title="Your next opportunity starts here"
          text="Add a brand and its competitors, then run your first visibility analysis."
          ><a routerLink="/brands/new" class="btn primary">Add your first brand →</a></app-empty
        >
      }
      <div class="card-grid">
        @for (brand of brands(); track brand.brand_id) {
          <article class="card brand-card">
            <div class="brand-card-head">
              <span class="brand-avatar">{{ brand.brand_name.charAt(0).toUpperCase() }}</span>
              <div>
                <h3>
                  <a [routerLink]="['/brands', brand.brand_id]">{{ brand.brand_name }}</a>
                </h3>
                <span class="muted small-text">Brand workspace</span>
              </div>
              <app-badge [status]="brand.latest_run_status || 'not measured'" />
            </div>
            <div class="brand-card-metrics">
              <div>
                <span class="eyebrow">Opportunities</span
                ><strong>{{ brand.opportunity_count }}</strong>
              </div>
              <div>
                <span class="eyebrow">Highest gap score</span
                ><strong>{{
                  brand.top_score === null ? '—' : (brand.top_score | number: '1.0-1')
                }}</strong>
              </div>
            </div>
            <div class="brand-card-footer">
              <span>{{
                brand.latest_run_finished_at
                  ? (brand.latest_run_finished_at | date: 'MMM d, HH:mm')
                  : 'No completed analysis yet'
              }}</span
              ><a [routerLink]="['/brands', brand.brand_id]">Open workspace ↗</a>
            </div>
          </article>
        }
      </div>
      <div class="notice" style="margin-top:24px">
        <strong>Opportunity is room to grow</strong>
        <p>
          A higher opportunity score means a bigger remaining visibility gap. Open a brand to see
          its evidence, recommendations and run history.
        </p>
      </div>
    }`,
})
export class OverviewPage {
  private readonly api = inject(ApiService);
  readonly loading = signal(true);
  readonly error = signal<Problem | null>(null);
  readonly brands = signal<BrandOverview[]>([]);
  readonly opportunities = computed(() =>
    this.brands().reduce((sum, b) => sum + b.opportunity_count, 0),
  );
  readonly completed = computed(
    () => this.brands().filter((b) => b.latest_run_status === 'succeeded').length,
  );
  readonly attention = computed(
    () =>
      this.brands().filter((b) => ['partial', 'failed'].includes(b.latest_run_status || '')).length,
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
