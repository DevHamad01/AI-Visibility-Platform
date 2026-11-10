import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { NgxEchartsDirective } from 'ngx-echarts';
import { EChartsCoreOption } from 'echarts/core';
import { ApiService } from '../core/api.service';
import { Brand, Competitor, Problem, RunSummary } from '../core/models';
import { problemOf } from '../core/errors';
import { ThemeService } from '../core/theme.service';
import { Badge, Empty, ErrorState, Loading, Stat } from '../shared/ui';
@Component({
  imports: [
    RouterLink,
    DatePipe,
    DecimalPipe,
    NgxEchartsDirective,
    Badge,
    Empty,
    ErrorState,
    Loading,
    Stat,
  ],
  template: ` <a class="back-link" routerLink="/">← Portfolio overview</a>
    @if (loading()) {
      <app-loading />
    } @else if (error(); as p) {
      <app-error [problem]="p" (retry)="load()" />
    } @else if (brand(); as b) {
      <div class="page-head">
        <div>
          <span class="eyebrow">Brand workspace · {{ b.domain }}</span>
          <h1>{{ b.name }}</h1>
          <p>{{ b.description || 'Your brand’s visibility across search and AI answers.' }}</p>
        </div>
        <div class="actions">
          <a class="btn" [routerLink]="['/brands', id, 'edit']">Brand settings</a
          ><button class="btn primary" (click)="start()" [disabled]="starting() || active()">
            {{ starting() ? 'Starting…' : active() ? 'Analysis in progress' : '↗ Run analysis' }}
          </button>
        </div>
      </div>
      @if (startError(); as p) {
        <app-error [problem]="p" (retry)="start()" />
      }
      @if (active(); as run) {
        <div class="notice">
          <strong>An analysis is in progress</strong>
          <p>
            Your data is being collected.
            <a [routerLink]="['/runs', run.id]">Watch live progress →</a>
          </p>
        </div>
      }
      <div class="stats">
        <app-stat label="Analyses" [value]="runs().length" detail="Most recent 100 runs" /><app-stat
          label="Latest opportunities"
          [value]="latest()?.metrics['opportunities'] ?? '—'"
          detail="From the latest analysis"
        /><app-stat
          label="Tracked competitors"
          [value]="competitors().length"
          detail="Your competitive landscape"
        /><app-stat
          label="Latest data cost"
          [value]="latest() ? '$' + (latest()!.dataforseo_cost_usd | number: '1.4-4') : '—'"
          detail="DataForSEO per-run spend"
        />
      </div>
      <div class="split">
        <section class="card">
          <h2>Opportunity trend</h2>
          <p class="muted small-text">Number of identified opportunities per completed analysis.</p>
          @if (measured().length) {
            <div
              echarts
              [options]="trend()"
              class="chart"
              aria-label="Opportunity count trend"
            ></div>
          } @else {
            <app-empty
              title="Your trend starts with a run"
              text="Completed analyses will appear here. Failed runs do not create measured trend points."
            />
          }
        </section>
        <section class="card">
          <h2>Competitive landscape</h2>
          <p class="muted small-text">Brands included in your next analysis.</p>
          <div class="info-row">
            <strong>{{ b.name }}</strong
            ><span>Your brand</span>
          </div>
          @for (c of competitors(); track c.id) {
            <div class="info-row">
              <strong>{{ c.name }}</strong
              ><span>{{ c.domain }}</span>
            </div>
          }
          @if (!competitors().length) {
            <p class="muted small-text" style="margin-top:20px">No competitors tracked yet.</p>
          }
          <a class="btn small" style="margin-top:20px" [routerLink]="['/brands', id, 'edit']"
            >Manage brand →</a
          >
        </section>
      </div>
      <div class="section-head">
        <div>
          <h2>Analysis history</h2>
          <p>Every run keeps its own results and trace.</p>
        </div>
        @if (runs().length >= 2) {
          <a class="btn small" [routerLink]="['/brands', id, 'compare']">Compare runs ⇄</a>
        }
      </div>
      @if (!runs().length) {
        <app-empty
          title="Ready for your first analysis?"
          text="Run an analysis to discover where your brand appears and where competitors are getting ahead."
          ><button class="btn primary" (click)="start()" [disabled]="starting()">
            Run first analysis →
          </button></app-empty
        >
      } @else {
        <div class="card flush table-scroll">
          <table>
            <thead>
              <tr>
                <th>Analysis</th>
                <th>Status</th>
                <th>Opportunities</th>
                <th>Provider</th>
                <th>Cost</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (run of runs(); track run.id) {
                <tr>
                  <td>
                    {{ run.created_at | date: 'MMM d, y · HH:mm' }}
                    <div class="mono muted">{{ run.id.slice(0, 8) }}</div>
                  </td>
                  <td><app-badge [status]="run.status" /></td>
                  <td>{{ run.metrics['opportunities'] ?? '—' }}</td>
                  <td>{{ run.llm_provider || '—' }}</td>
                  <td class="number">{{ run.dataforseo_cost_usd | number: '1.4-4' }} USD</td>
                  <td><a [routerLink]="['/runs', run.id]">Open →</a></td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
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
  readonly trend = computed<EChartsCoreOption>(() => ({
    aria: { enabled: true },
    textStyle: { color: this.theme.dark() ? '#a3acc1' : '#70778a', fontFamily: 'system-ui' },
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 15, top: 25, bottom: 35 },
    xAxis: {
      type: 'category',
      data: this.measured().map((r) => new Date(r.created_at).toLocaleDateString()),
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: this.theme.dark() ? '#30374b' : '#e5e8ef' } },
    },
    series: [
      {
        type: 'line',
        data: this.measured().map((r) => r.metrics['opportunities']),
        smooth: true,
        symbolSize: 8,
        lineStyle: { color: '#7770ed', width: 3 },
        itemStyle: { color: '#7770ed' },
        areaStyle: { color: '#7770ed', opacity: 0.08 },
      },
    ],
  }));
  private startKey = crypto.randomUUID();
  constructor() {
    this.load();
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
