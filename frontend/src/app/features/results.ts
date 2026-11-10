import { Component, DestroyRef, computed, effect, inject, input, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin, Subscription } from 'rxjs';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { ApiService } from '../core/api.service';
import {
  Opportunity,
  Problem,
  Recommendation,
  RecommendationStatus,
  VisibilityQuery,
} from '../core/models';
import { problemOf } from '../core/errors';
import { ThemeService } from '../core/theme.service';
import { Empty, ErrorState, Loading } from '../shared/ui';
const CHANNELS = [
  { key: 'google_organic', label: 'Google organic' },
  { key: 'google_ai_overview', label: 'AI Overview' },
  { key: 'llm_chatgpt', label: 'ChatGPT' },
  { key: 'llm_google_ai', label: 'Google AI' },
];
@Component({
  selector: 'app-results',
  imports: [FormsModule, DecimalPipe, NgxEchartsDirective, Empty, ErrorState, Loading],
  template: `
    @if (loading()) {
      <app-loading />
    } @else if (error(); as p) {
      <app-error [problem]="p" (retry)="load()" />
    } @else {
      <div class="section-head">
        <div>
          <h2>Visibility landscape</h2>
          <p>Where your brand appears across measured queries and channels.</p>
        </div>
        <div class="actions">
          <a class="btn small" [href]="api.exportUrl(runId(), 'csv')" download>↓ CSV</a
          ><a class="btn small" [href]="api.exportUrl(runId(), 'json')" download>↓ JSON</a>
        </div>
      </div>
      @if (!queries().length) {
        <app-empty
          title="No visibility data yet"
          text="This run did not collect query observations. Check the stage trace for the provider’s response before starting another analysis."
        />
      } @else {
        <section class="card">
          <div class="filters">
            <div>
              <label for="entity">Show visibility for</label
              ><select id="entity" [ngModel]="entity()" (ngModelChange)="entity.set($event)">
                <option value="brand">Your brand</option>
                @for (name of competitorNames(); track name) {
                  <option [value]="name">{{ name }}</option>
                }
              </select>
            </div>
            <p class="field-help" style="flex:2">
              Visible = presence recorded · Absent = measured but not present · — = no observation
            </p>
          </div>
          <div
            echarts
            class="chart"
            [style.height.px]="Math.max(250, queries().length * 35 + 95)"
            [options]="heatmap()"
            aria-label="Visibility matrix chart"
          ></div>
          <details>
            <summary>View accessible data table and citations</summary>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Query</th>
                    @for (c of channels; track c.key) {
                      <th>{{ c.label }}</th>
                    }
                    <th>Competitors & sources</th>
                  </tr>
                </thead>
                <tbody>
                  @for (q of queries(); track q.id) {
                    <tr>
                      <td>{{ q.text }}</td>
                      @for (c of channels; track c.key) {
                        <td [class.measured]="presence(q, c.key) === 1">
                          {{
                            presence(q, c.key) === null
                              ? '—'
                              : presence(q, c.key)
                                ? 'Visible'
                                : 'Absent'
                          }}
                        </td>
                      }
                      <td>
                        @for (o of q.observations; track $index) {
                          <div class="small-text">
                            {{ o.channel.replaceAll('_', ' ') }}:
                            {{ o.competitors_visible.join(', ') || 'No competitors recorded' }}
                            @for (url of o.cited_urls; track $index) {
                              @if (safeUrl(url)) {
                                <div>
                                  <a [href]="url" target="_blank" rel="noopener noreferrer">{{
                                    url
                                  }}</a>
                                </div>
                              }
                            }
                          </div>
                        }
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </details>
        </section>
      }
      <div class="section-head">
        <div>
          <h2>Find your next move</h2>
          <p>Ranked gaps, grounded in demand and competitive evidence.</p>
        </div>
        <span class="eyebrow">{{ opportunities().length }} opportunities</span>
      </div>
      <section class="card">
        <form class="filters" (ngSubmit)="filter()">
          <div>
            <label for="search">Search queries</label
            ><input
              id="search"
              name="search"
              [(ngModel)]="search"
              placeholder="Find an opportunity…"
            />
          </div>
          <div>
            <label for="minimum">Minimum score</label
            ><input
              id="minimum"
              name="minimum"
              type="number"
              min="0"
              max="100"
              [(ngModel)]="minimum"
            />
          </div>
          <div>
            <label for="intent">Intent</label
            ><select id="intent" name="intent" [(ngModel)]="intent">
              <option value="">All intents</option>
              @for (i of intents(); track i) {
                <option [value]="i">{{ i }}</option>
              }
            </select>
          </div>
          <div>
            <label for="channel">Channel</label
            ><select id="channel" name="channel" [(ngModel)]="channel">
              <option value="">All channels</option>
              @for (c of channels; track c.key) {
                <option [value]="c.key">{{ c.label }}</option>
              }
            </select>
          </div>
          <div>
            <label for="sort">Sort</label
            ><select id="sort" name="sort" [(ngModel)]="sort">
              <option value="score_desc">Highest score</option>
              <option value="score_asc">Lowest score</option>
            </select>
          </div>
          <button class="btn primary" type="submit" [disabled]="filtering()">
            {{ filtering() ? 'Filtering…' : 'Apply' }}
          </button>
        </form>
        @if (filterError(); as p) {
          <app-error [problem]="p" (retry)="filter()" />
        }
        @if (!opportunities().length) {
          <app-empty
            title="No matching opportunities"
            text="Try a broader filter, or check the trace if this analysis did not collect enough data."
          />
        } @else {
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Search query</th>
                  <th>Opportunity score</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                @for (o of opportunities(); track o.id) {
                  <tr>
                    <td class="muted">{{ o.rank.toString().padStart(2, '0') }}</td>
                    <td>
                      <button class="text-link" (click)="selected.set(o); scoreDialog.showModal()">
                        {{ o.query_text }}
                      </button>
                    </td>
                    <td>
                      <span class="score">{{ o.score | number: '1.1-1' }}</span
                      ><span class="muted"> / 100</span>
                    </td>
                    <td>
                      <button class="btn small" (click)="selected.set(o); scoreDialog.showModal()">
                        Score breakdown ↗
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
        <p class="field-help" style="margin-top:16px">
          Showing up to 200 opportunities. Higher scores indicate larger remaining gaps.
        </p>
      </section>
      <div class="section-head">
        <div>
          <h2>Turn insight into action</h2>
          <p>Recommendations generated from your measured opportunities.</p>
        </div>
      </div>
      @if (actionError(); as p) {
        <app-error [problem]="p" (retry)="actionError.set(null)" />
      }
      @if (!recommendations().length) {
        <app-empty
          title="Recommendations will appear here"
          text="A run needs scored opportunities and a successful recommendation stage before it can suggest content actions."
        />
      } @else {
        <div class="board">
          @for (column of columns; track column.key) {
            <section class="board-column">
              <h3>{{ column.label }} · {{ byStatus(column.key).length }}</h3>
              @for (r of byStatus(column.key); track r.id) {
                <article class="recommendation">
                  <span class="eyebrow">{{ r.content_type.replaceAll('_', ' ') }}</span>
                  <h3>{{ r.title }}</h3>
                  <p>{{ r.rationale }}</p>
                  @if (r.target_query) {
                    <p><strong>Target:</strong> {{ r.target_query }}</p>
                  }
                  @if (r.outline?.length) {
                    <details>
                      <summary>Content outline</summary>
                      <ol>
                        @for (line of r.outline; track $index) {
                          <li>{{ line }}</li>
                        }
                      </ol>
                    </details>
                  }
                  <p>
                    {{ r.priority || 'Unspecified' }} priority ·
                    {{ r.effort || 'Unspecified' }} effort
                  </p>
                  <label class="small-text" [for]="'status-' + r.id">Move to</label
                  ><select
                    [id]="'status-' + r.id"
                    [ngModel]="r.status"
                    (ngModelChange)="move(r, $event)"
                    [disabled]="updating().includes(r.id)"
                  >
                    @for (c of columns; track c.key) {
                      <option [value]="c.key">{{ c.label }}</option>
                    }
                  </select>
                </article>
              }
            </section>
          }
        </div>
      }
    }
    <dialog
      #scoreDialog
      class="score-dialog"
      (close)="selected.set(null)"
      aria-labelledby="score-title"
    >
      @if (selected(); as o) {
        <div class="drawer-head">
          <span class="eyebrow">Explainable by design</span
          ><button
            class="btn small"
            (click)="scoreDialog.close()"
            aria-label="Close score breakdown"
          >
            ✕
          </button>
        </div>
        <h2 id="score-title">{{ o.query_text }}</h2>
        <p class="score" style="font-size:44px;margin:24px 0">
          {{ o.score | number: '1.1-1' }}<span class="muted" style="font-size:16px"> / 100</span>
        </p>
        <p>
          {{
            o.explanation || 'This score is calculated from observed data using the formula below.'
          }}
        </p>
        <h3>Score components</h3>
        @for (c of components(o); track c.key) {
          <div class="component-row">
            <span>{{ c.key }}</span
            ><strong>{{ c.value }}</strong>
          </div>
        }
        <div class="notice" style="margin-top:24px">
          <strong>The opportunity formula</strong>
          <p class="mono">100 × demand × gap × (0.6 + 0.4 × contested) × (1 − 0.5 × difficulty)</p>
          <p>
            Demand is log-scaled search volume. Gap is one minus measured visibility. Contested is
            the share of tracked competitors present. Difficulty is normalized to 0–1.
          </p>
        </div>
      }
    </dialog>
  `,
})
export class ResultsPanel {
  readonly api = inject(ApiService);
  private readonly destroy = inject(DestroyRef);
  private readonly theme = inject(ThemeService);
  readonly runId = input.required<string>();
  readonly status = input.required<string>();
  readonly channels = CHANNELS;
  readonly Math = Math;
  readonly queries = signal<VisibilityQuery[]>([]);
  readonly opportunities = signal<Opportunity[]>([]);
  readonly recommendations = signal<Recommendation[]>([]);
  readonly entity = signal('brand');
  readonly selected = signal<Opportunity | null>(null);
  readonly loading = signal(true);
  readonly filtering = signal(false);
  readonly updating = signal<string[]>([]);
  readonly error = signal<Problem | null>(null);
  readonly filterError = signal<Problem | null>(null);
  readonly actionError = signal<Problem | null>(null);
  search = '';
  minimum: number | null = null;
  intent = '';
  channel = '';
  sort = 'score_desc';
  private filterRequest?: Subscription;
  private loadRequest?: Subscription;
  readonly columns: { key: RecommendationStatus; label: string }[] = [
    { key: 'todo', label: 'To do' },
    { key: 'in_progress', label: 'In progress' },
    { key: 'done', label: 'Done' },
    { key: 'dismissed', label: 'Dismissed' },
  ];
  readonly competitorNames = computed(() =>
    [
      ...new Set(
        this.queries().flatMap((q) => q.observations.flatMap((o) => o.competitors_visible)),
      ),
    ].sort(),
  );
  readonly intents = computed(() =>
    [
      ...new Set(
        this.queries()
          .map((q) => q.intent)
          .filter((i): i is string => !!i),
      ),
    ].sort(),
  );
  readonly heatmap = computed<EChartsCoreOption>(() => ({
    aria: { enabled: true },
    animation: false,
    textStyle: { color: this.theme.dark() ? '#a3acc1' : '#70778a', fontFamily: 'system-ui' },
    grid: { left: 190, right: 20, top: 10, bottom: 60 },
    tooltip: {
      formatter: (value: unknown) => {
        const item = value as { value?: number[] };
        const v = item.value;
        return v ? `${CHANNELS[v[0]].label}: ${v[2] ? 'Visible' : 'Absent'}` : '';
      },
    },
    xAxis: {
      type: 'category',
      data: CHANNELS.map((c) => c.label),
      axisLine: { show: false },
      axisTick: { show: false },
      splitArea: { show: false },
      axisLabel: { fontSize: 10, interval: 0 },
    },
    yAxis: {
      type: 'category',
      data: this.queries().map((q) => q.text),
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { width: 170, overflow: 'truncate', fontSize: 11 },
    },
    visualMap: {
      type: 'piecewise',
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      pieces: [
        { value: 0, label: 'Measured absence', color: this.theme.dark() ? '#30374b' : '#e5e8ef' },
        { value: 1, label: 'Visible', color: '#7770ed' },
      ],
      textStyle: { color: this.theme.dark() ? '#a3acc1' : '#70778a' },
    },
    series: [
      {
        type: 'heatmap',
        label: {
          show: true,
          formatter: (value: unknown) => {
            const v = value as { value: number[] };
            return v.value[2] ? '✓' : '–';
          },
          color: this.theme.dark() ? '#fff' : '#202437',
        },
        itemStyle: {
          borderWidth: 5,
          borderColor: this.theme.dark() ? '#1a1e2d' : '#fff',
          borderRadius: 7,
        },
        data: this.queries().flatMap((q, y) =>
          CHANNELS.flatMap((c, x) => {
            const p = this.presence(q, c.key);
            return p === null ? [] : [[x, y, p]];
          }),
        ),
      },
    ],
  }));
  constructor() {
    effect(() => {
      this.runId();
      this.load();
    });
  }
  load() {
    this.loadRequest?.unsubscribe();
    this.loading.set(true);
    this.error.set(null);
    this.loadRequest = forkJoin({
      visibility: this.api.visibility(this.runId()),
      opportunities: this.api.opportunities(this.runId()),
      recommendations: this.api.recommendations(this.runId()),
    })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.queries.set(data.visibility.queries);
          this.opportunities.set(data.opportunities.items);
          this.recommendations.set(data.recommendations.items);
          this.loading.set(false);
        },
        error: (e) => {
          this.error.set(problemOf(e));
          this.loading.set(false);
        },
      });
  }
  presence(q: VisibilityQuery, channel: string): number | null {
    const observations = q.observations.filter((o) => o.channel === channel);
    if (!observations.length) return null;
    return observations.some((o) =>
      this.entity() === 'brand' ? o.brand_visible : o.competitors_visible.includes(this.entity()),
    )
      ? 1
      : 0;
  }
  safeUrl(url: string) {
    try {
      return ['https:', 'http:'].includes(new URL(url).protocol);
    } catch {
      return false;
    }
  }
  filter() {
    if (this.minimum !== null && (this.minimum < 0 || this.minimum > 100)) return;
    this.filterRequest?.unsubscribe();
    const filters: Record<string, string | number> = { sort: this.sort };
    if (this.search.trim()) filters['q'] = this.search.trim();
    if (this.minimum !== null) filters['min_score'] = this.minimum;
    if (this.intent) filters['intent'] = this.intent;
    if (this.channel) filters['channel'] = this.channel;
    this.filtering.set(true);
    this.filterError.set(null);
    this.filterRequest = this.api
      .opportunities(this.runId(), filters)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (p) => {
          this.opportunities.set(p.items);
          this.filtering.set(false);
        },
        error: (e) => {
          this.filterError.set(problemOf(e));
          this.filtering.set(false);
        },
      });
  }
  byStatus(status: RecommendationStatus) {
    return this.recommendations().filter((r) => r.status === status);
  }
  move(r: Recommendation, status: RecommendationStatus) {
    this.updating.update((ids) => [...ids, r.id]);
    this.actionError.set(null);
    this.api
      .updateRecommendation(r.id, status)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (updated) => {
          this.recommendations.update((items) =>
            items.map((item) => (item.id === r.id ? updated : item)),
          );
          this.updating.update((ids) => ids.filter((id) => id !== r.id));
        },
        error: (e) => {
          this.actionError.set(problemOf(e));
          this.updating.update((ids) => ids.filter((id) => id !== r.id));
        },
      });
  }
  components(o: Opportunity) {
    return Object.entries(o.components).map(([key, value]) => ({
      key: key.replaceAll('_', ' '),
      value: typeof value === 'number' ? value.toFixed(4) : JSON.stringify(value),
    }));
  }
}
