import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { forkJoin } from 'rxjs';
import { ApiService } from '../core/api.service';
import { problemOf } from '../core/errors';
import { Brand, Competitor, Problem, RunSummary } from '../core/models';
import { ThemeService } from '../core/theme.service';
import { baseChartOptions, chartTheme } from '../shared/echarts';
import { Icon } from '../shared/icon';
import { Empty, ErrorState, PageHeader, Section, Skeleton, Stat, StatusBadge } from '../shared/ui';

@Component({
  imports: [
    RouterLink,
    DatePipe,
    DecimalPipe,
    NgxEchartsDirective,
    Icon,
    Empty,
    ErrorState,
    PageHeader,
    Section,
    Skeleton,
    Stat,
    StatusBadge,
  ],
  template: `<a
      routerLink="/"
      class="mb-5 inline-flex items-center gap-1.5 text-label-sm font-medium text-ink-600 transition-colors duration-150 hover:text-ink-950"
    >
      <app-icon name="arrow-left" [size]="14" /> Overview
    </a>

    @if (loading()) {
      <app-skeleton variant="stats" />
      <div class="mt-6"><app-skeleton variant="table" /></div>
    } @else if (error(); as problem) {
      <app-error [problem]="problem" (retry)="load()" />
    } @else if (brand(); as b) {
      <app-page-header [eyebrow]="b.domain" [title]="b.name" [subtitle]="b.description || ''">
        <a class="btn-secondary" [routerLink]="['/brands', id, 'edit']">
          <app-icon name="building" [size]="14" /> Settings
        </a>
        @if (runs().length >= 2) {
          <a class="btn-secondary" [routerLink]="['/brands', id, 'compare']">
            <app-icon name="compare" [size]="14" /> Compare
          </a>
        }
        <button class="btn-primary" (click)="start()" [disabled]="starting() || !!active()">
          @if (starting()) {
            <app-icon name="spinner" [size]="14" /> Starting…
          } @else if (active()) {
            <app-icon name="spinner" [size]="14" /> Running
          } @else {
            <app-icon name="play" [size]="14" /> Run analysis
          }
        </button>
      </app-page-header>

      @if (startError(); as problem) {
        <div class="mb-4"><app-error [problem]="problem" (retry)="start()" /></div>
      }

      @if (active(); as run) {
        <div
          class="card mb-4 flex flex-wrap items-center gap-3 p-3.5"
          style="background: rgb(var(--brand-500) / 0.05)"
          role="status"
        >
          <span class="relative flex h-2 w-2 shrink-0">
            <span class="absolute inset-0 animate-pulse-ring rounded-full bg-brand-500"></span>
            <span class="relative h-2 w-2 rounded-full bg-brand-500"></span>
          </span>
          <p class="min-w-0 flex-1 text-label-sm text-ink-700">
            <span class="font-semibold text-ink-950">An analysis is running.</span>
            Data is being collected from DataForSEO and your LLM provider.
          </p>
          <a [routerLink]="['/runs', run.id]" class="btn-tinted btn-sm">
            Watch live <app-icon name="arrow-right" [size]="12" />
          </a>
        </div>
      }

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="card p-4">
          <app-stat label="Analyses" [value]="runs().length" detail="most recent first" />
        </div>
        <div class="card p-4">
          <app-stat
            label="Latest opportunities"
            [value]="latest()?.metrics['opportunities'] ?? '—'"
            [detail]="latest() ? 'from the last run' : 'no runs yet'"
          />
        </div>
        <div class="card p-4">
          <app-stat
            label="Competitors"
            [value]="competitors().length"
            detail="measured against you"
          />
        </div>
        <div class="card p-4">
          <app-stat
            label="Latest data cost"
            [value]="latest() ? '$' + (latest()!.dataforseo_cost_usd | number: '1.4-4') : '—'"
            detail="DataForSEO spend"
          />
        </div>
      </div>

      <div class="mt-6 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <app-section
          title="Opportunity trend"
          subtitle="Opportunities found per completed analysis"
        >
          @if (measured().length >= 2) {
            <div
              echarts
              [options]="trend()"
              class="h-[240px] w-full p-2"
              aria-label="Opportunity count per completed analysis"
            ></div>
          } @else {
            <app-empty
              icon="bar-chart"
              title="Trend needs two runs"
              [text]="
                measured().length === 1
                  ? 'One completed analysis so far. Run another to see movement over time.'
                  : 'Completed analyses appear here. Failed runs produce no trend point.'
              "
            />
          }
        </app-section>

        <app-section title="Measured against" [subtitle]="competitors().length + ' competitors'">
          <ul class="divide-y-hairline divide-stroke-200">
            <li class="flex items-center gap-3 px-4 py-2.5">
              <span
                class="grid h-7 w-7 shrink-0 place-items-center rounded-6 bg-brand-500 text-label-xs font-semibold text-white"
                >{{ b.name.charAt(0).toUpperCase() }}</span
              >
              <span class="min-w-0 flex-1">
                <span class="block truncate text-label-sm font-medium text-ink-950">{{
                  b.name
                }}</span>
                <span class="block truncate text-label-xs text-ink-400">{{ b.domain }}</span>
              </span>
              <span class="badge-brand">You</span>
            </li>
            @for (c of competitors(); track c.id) {
              <li class="flex items-center gap-3 px-4 py-2.5">
                <span
                  class="grid h-7 w-7 shrink-0 place-items-center rounded-6 border-hairline border-stroke-200 bg-surface-50 text-label-xs font-semibold text-ink-600"
                  >{{ c.name.charAt(0).toUpperCase() }}</span
                >
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-label-sm font-medium text-ink-950">{{
                    c.name
                  }}</span>
                  <span class="block truncate text-label-xs text-ink-400">{{ c.domain }}</span>
                </span>
              </li>
            }
          </ul>
          @if (!competitors().length) {
            <app-empty
              icon="building"
              title="No competitors yet"
              text="Scores need competitors to measure how contested each query is."
            >
              <a class="btn-secondary btn-sm" [routerLink]="['/brands', id, 'edit']">
                <app-icon name="plus" [size]="12" /> Add competitors
              </a>
            </app-empty>
          }
        </app-section>
      </div>

      <div class="mt-6">
        @if (!runs().length) {
          <div class="card">
            <app-empty
              icon="play"
              title="Run your first analysis"
              text="Signal plans the searches, measures where you and your competitors appear, scores every gap, then writes content recommendations for the biggest ones."
            >
              <button class="btn-primary" (click)="start()" [disabled]="starting()">
                <app-icon name="play" [size]="14" /> Run analysis
              </button>
            </app-empty>
          </div>
        } @else {
          <app-section title="Analysis history" subtitle="Each run keeps its own results and trace">
            <div class="overflow-x-auto">
              <table class="tbl tbl-interactive">
                <thead>
                  <tr>
                    <th>Started</th>
                    <th>Status</th>
                    <th class="text-right">Queries</th>
                    <th class="text-right">Opportunities</th>
                    <th>Provider</th>
                    <th class="text-right">Cost</th>
                    <th class="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  @for (run of runs(); track run.id) {
                    <tr (click)="open(run.id)">
                      <td>
                        <span class="block whitespace-nowrap text-label-sm text-ink-950">{{
                          run.created_at | date: 'MMM d, y · HH:mm'
                        }}</span>
                        <span class="tnum block text-label-xs text-ink-400">{{
                          run.id.slice(0, 8)
                        }}</span>
                      </td>
                      <td><app-status-badge [status]="run.status" /></td>
                      <td class="tnum text-right">{{ run.metrics['queries'] ?? '—' }}</td>
                      <td class="tnum text-right font-medium text-ink-950">
                        {{ run.metrics['opportunities'] ?? '—' }}
                      </td>
                      <td>
                        @if (run.llm_provider) {
                          <span class="badge-neutral">{{ run.llm_provider }}</span>
                        } @else {
                          <span class="text-ink-400">—</span>
                        }
                      </td>
                      <td class="tnum whitespace-nowrap text-right">
                        \${{ run.dataforseo_cost_usd | number: '1.4-4' }}
                      </td>
                      <td class="text-right text-ink-400">
                        <app-icon name="chevron-right" [size]="16" />
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </app-section>
        }
      </div>
    }`,
})
export class BrandDetailPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly theme = inject(ThemeService);

  readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly brand = signal<Brand | null>(null);
  readonly competitors = signal<Competitor[]>([]);
  readonly runs = signal<RunSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal<Problem | null>(null);
  readonly startError = signal<Problem | null>(null);
  readonly starting = signal(false);

  readonly latest = computed(() => this.runs().at(0));
  readonly active = computed(() =>
    this.runs().find((r) => ['queued', 'running'].includes(r.status)),
  );
  readonly measured = computed(() =>
    this.runs()
      .filter(
        (r) =>
          ['succeeded', 'partial'].includes(r.status) && r.metrics['opportunities'] !== undefined,
      )
      .toReversed(),
  );

  readonly trend = computed<EChartsCoreOption>(() => {
    // Depend on the theme signal so the chart re-renders on toggle.
    this.theme.dark();
    const t = chartTheme();
    return {
      ...baseChartOptions(t),
      tooltip: { ...baseChartOptions(t).tooltip, trigger: 'axis' },
      grid: { left: 36, right: 16, top: 16, bottom: 28 },
      xAxis: {
        type: 'category',
        data: this.measured().map((r) => new Date(r.created_at).toLocaleDateString()),
        axisLine: { lineStyle: { color: t.grid } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: t.grid } },
      },
      series: [
        {
          type: 'line',
          name: 'Opportunities',
          data: this.measured().map((r) => r.metrics['opportunities']),
          smooth: 0.3,
          symbolSize: 8,
          lineStyle: { color: t.brand, width: 2 },
          itemStyle: { color: t.brand, borderColor: t.surface, borderWidth: 2 },
          areaStyle: { color: t.brand, opacity: 0.08 },
        },
      ],
    };
  });

  private startKey = crypto.randomUUID();

  constructor() {
    this.load();
  }

  open(runId: string) {
    void this.router.navigate(['/runs', runId]);
  }

  load() {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      brand: this.api.brand(this.id),
      competitors: this.api.competitors(this.id),
      runs: this.api.runs(this.id),
    }).subscribe({
      next: (data) => {
        this.brand.set(data.brand);
        this.competitors.set(data.competitors);
        this.runs.set(data.runs.items);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(problemOf(e));
        this.loading.set(false);
      },
    });
  }

  start() {
    if (this.starting() || this.active()) return;
    this.starting.set(true);
    this.startError.set(null);
    this.api.startRun(this.id, this.startKey).subscribe({
      next: (run) => {
        // A fresh key per accepted run, so the next click is a new run and a
        // retry of *this* click is still idempotent.
        this.startKey = crypto.randomUUID();
        void this.router.navigate(['/runs', run.id]);
      },
      error: (e) => {
        this.startError.set(problemOf(e));
        this.starting.set(false);
      },
    });
  }
}
