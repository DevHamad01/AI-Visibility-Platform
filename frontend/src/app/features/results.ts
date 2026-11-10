import { DecimalPipe } from '@angular/common';
import { Component, DestroyRef, computed, effect, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Subscription, forkJoin } from 'rxjs';
import { ApiService } from '../core/api.service';
import { problemOf } from '../core/errors';
import {
  Opportunity,
  Problem,
  Recommendation,
  RecommendationStatus,
  VisibilityQuery,
} from '../core/models';
import { Icon, IconName } from '../shared/icon';
import { Empty, ErrorState, ScoreMeter, Section, Skeleton } from '../shared/ui';

/**
 * Fixed channel order. The index also picks the colour slot, so a channel
 * keeps the same colour everywhere in the app.
 */
const CHANNELS: { key: string; label: string; short: string }[] = [
  { key: 'google_organic', label: 'Google organic', short: 'Organic' },
  { key: 'google_ai_overview', label: 'AI Overview', short: 'AI Ovw' },
  { key: 'llm_chatgpt', label: 'ChatGPT', short: 'ChatGPT' },
  { key: 'llm_google_ai', label: 'Google AI', short: 'Google AI' },
];

/** How to read each score component in the breakdown drawer. */
const COMPONENT_COPY: Record<string, { label: string; what: string }> = {
  demand: { label: 'Demand', what: 'Log-scaled search volume, capped at 50k/mo' },
  visibility: { label: 'Visibility', what: 'How present you already are across channels' },
  gap: { label: 'Gap', what: '1 − visibility: the room left to win' },
  contested: { label: 'Contested', what: 'Share of tracked competitors already present' },
  difficulty: { label: 'Difficulty', what: 'Keyword difficulty, normalised to 0–1' },
  score: { label: 'Final score', what: 'The 0–100 opportunity' },
};

@Component({
  selector: 'app-results',
  imports: [FormsModule, DecimalPipe, Icon, Empty, ErrorState, ScoreMeter, Section, Skeleton],
  template: `@if (loading()) {
      <app-skeleton variant="table" />
    } @else if (error(); as problem) {
      <app-error [problem]="problem" (retry)="load()" />
    } @else {
      <div class="space-y-4">
        <!-- ========== Visibility matrix ========== -->
        <app-section
          title="Visibility matrix"
          [subtitle]="
            queries().length
              ? queries().length + ' queries measured across ' + channels.length + ' channels'
              : 'No observations collected'
          "
        >
          <div toolbar>
            <a class="btn-secondary btn-sm" [href]="api.exportUrl(runId(), 'csv')" download>
              <app-icon name="download" [size]="12" /> CSV
            </a>
            <a class="btn-secondary btn-sm" [href]="api.exportUrl(runId(), 'json')" download>
              <app-icon name="download" [size]="12" /> JSON
            </a>
          </div>

          @if (!queries().length) {
            <app-empty
              icon="eye-off"
              title="No visibility data in this run"
              text="No query observations were stored, so there is nothing to plot. The stage trace records exactly what each provider returned."
            />
          } @else {
            <!-- Entity switcher -->
            <div
              class="flex flex-wrap items-center gap-x-3 gap-y-2 border-b-hairline border-stroke-200 px-4 py-3"
            >
              <span class="eyebrow">Showing</span>
              <div
                class="inline-flex flex-wrap items-center gap-1 rounded-8 border-hairline border-stroke-200 bg-surface-50 p-1"
                role="group"
                aria-label="Whose visibility to show"
              >
                <button type="button" [class]="pillCls('brand')" (click)="entity.set('brand')">
                  Your brand
                </button>
                @for (name of competitorNames(); track name) {
                  <button type="button" [class]="pillCls(name)" (click)="entity.set(name)">
                    {{ name }}
                  </button>
                }
              </div>

              <p
                class="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-label-xs text-ink-400"
              >
                <span class="flex items-center gap-1.5">
                  <span class="h-2.5 w-2.5 rounded-[3px] bg-chart-1"></span>visible
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="h-2.5 w-2.5 rounded-[3px] bg-surface-200"></span>absent
                </span>
                <span class="flex items-center gap-1.5">
                  <span
                    class="h-2.5 w-2.5 rounded-[3px] border-hairline border-dashed border-stroke-300"
                  ></span
                  >not measured
                </span>
              </p>
            </div>

            <!-- A real table, so screen readers can read it and no cell depends
                 on colour alone — each one also carries a glyph. -->
            <div class="overflow-x-auto">
              <table class="w-full border-separate border-spacing-0 text-left">
                <caption class="sr-only">
                  Visibility of
                  {{
                    entity() === 'brand' ? 'your brand' : entity()
                  }}
                  per query and channel
                </caption>
                <thead>
                  <tr>
                    <th
                      scope="col"
                      class="sticky left-0 z-10 min-w-[240px] bg-surface-0 px-4 py-2.5 text-label-xs font-medium uppercase tracking-[0.06em] text-ink-400"
                    >
                      Query
                    </th>
                    @for (c of channels; track c.key) {
                      <th
                        scope="col"
                        class="w-[86px] px-1 py-2.5 text-center text-label-xs font-medium text-ink-600"
                      >
                        <span class="hidden sm:inline">{{ c.label }}</span>
                        <span class="sm:hidden">{{ c.short }}</span>
                      </th>
                    }
                    <th
                      scope="col"
                      class="w-[92px] px-3 py-2.5 text-right text-label-xs font-medium uppercase tracking-[0.06em] text-ink-400"
                    >
                      Volume
                    </th>
                  </tr>
                </thead>
                <tbody>
                  @for (q of queries(); track q.id) {
                    <tr class="group">
                      <th
                        scope="row"
                        class="sticky left-0 z-10 border-t-hairline border-stroke-200 bg-surface-0 px-4 py-2 font-normal group-hover:bg-surface-50"
                      >
                        <span class="block truncate text-label-sm font-medium text-ink-950">{{
                          q.text
                        }}</span>
                        <span class="mt-0.5 flex items-center gap-1.5">
                          <span class="badge-neutral">{{ q.source.replaceAll('_', ' ') }}</span>
                          @if (q.intent) {
                            <span class="text-label-xs text-ink-400">{{ q.intent }}</span>
                          }
                        </span>
                      </th>
                      @for (c of channels; track c.key; let i = $index) {
                        <td
                          class="border-t-hairline border-stroke-200 px-1 py-2 text-center align-middle group-hover:bg-surface-50"
                        >
                          @switch (presence(q, c.key)) {
                            @case (1) {
                              <span
                                class="inline-grid h-7 w-full max-w-[72px] place-items-center rounded-6 text-white"
                                [style.background]="channelColor(i)"
                                [title]="cellTitle(q, c.label, 1)"
                              >
                                <app-icon name="check" [size]="14" />
                                <span class="sr-only">visible</span>
                              </span>
                            }
                            @case (0) {
                              <span
                                class="inline-grid h-7 w-full max-w-[72px] place-items-center rounded-6 bg-surface-200 text-ink-400"
                                [title]="cellTitle(q, c.label, 0)"
                              >
                                <app-icon name="minus" [size]="14" />
                                <span class="sr-only">absent</span>
                              </span>
                            }
                            @default {
                              <span
                                class="inline-grid h-7 w-full max-w-[72px] place-items-center rounded-6 border-hairline border-dashed border-stroke-300 text-label-xs text-ink-400"
                                [title]="cellTitle(q, c.label, null)"
                              >
                                <span aria-hidden="true">&middot;</span>
                                <span class="sr-only">not measured</span>
                              </span>
                            }
                          }
                        </td>
                      }
                      <td
                        class="tnum border-t-hairline border-stroke-200 px-3 py-2 text-right text-label-sm text-ink-600 group-hover:bg-surface-50"
                      >
                        @if (q.search_volume !== null) {
                          {{ q.search_volume | number }}
                        } @else {
                          <span class="text-ink-400">&mdash;</span>
                        }
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>

            <!-- Competitors and cited sources, behind a disclosure so the
                 matrix above stays scannable. -->
            <details class="group border-t-hairline border-stroke-200">
              <summary
                class="flex cursor-pointer select-none items-center gap-1.5 px-4 py-3 text-label-sm font-medium text-ink-600 transition-colors duration-150 hover:text-ink-950"
              >
                <app-icon
                  name="chevron-right"
                  [size]="14"
                  class="transition-transform duration-150 group-open:rotate-90"
                />
                Competitors seen and sources cited
              </summary>
              <ul class="divide-y-hairline divide-stroke-200 border-t-hairline border-stroke-200">
                @for (q of queries(); track q.id) {
                  <li class="px-4 py-3">
                    <p class="text-label-sm font-medium text-ink-950">{{ q.text }}</p>
                    <ul class="mt-1.5 space-y-1.5">
                      @for (o of q.observations; track $index) {
                        <li class="text-label-xs leading-[16px]">
                          <span class="font-medium text-ink-700">{{
                            channelLabel(o.channel)
                          }}</span>
                          <span class="text-ink-600">
                            &middot;
                            @if (o.brand_visible) {
                              you are visible{{
                                o.brand_position !== null ? ' at position ' + o.brand_position : ''
                              }}
                            } @else {
                              you are absent
                            }
                            @if (o.competitors_visible.length) {
                              &middot; competitors: {{ o.competitors_visible.join(', ') }}
                            }
                          </span>
                          @for (url of o.cited_urls; track $index) {
                            @if (safeUrl(url)) {
                              <a
                                [href]="url"
                                target="_blank"
                                rel="noopener noreferrer"
                                class="link mt-0.5 block truncate"
                                >{{ url }}</a
                              >
                            }
                          }
                        </li>
                      } @empty {
                        <li class="text-label-xs text-ink-400">No observations for this query.</li>
                      }
                    </ul>
                  </li>
                }
              </ul>
            </details>
          }
        </app-section>

        <!-- ========== Opportunities ========== -->
        <app-section
          title="Opportunities"
          [subtitle]="opportunities().length + ' scored gaps, biggest first'"
        >
          <form
            class="flex flex-wrap items-end gap-2.5 border-b-hairline border-stroke-200 px-4 py-3"
            (ngSubmit)="filter()"
          >
            <div class="min-w-[170px] flex-1">
              <label class="field-label" for="search">Search</label>
              <div class="relative">
                <span
                  class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400"
                >
                  <app-icon name="search" [size]="14" />
                </span>
                <input
                  id="search"
                  name="search"
                  [(ngModel)]="search"
                  placeholder="Filter queries…"
                  class="input pl-8"
                />
              </div>
            </div>
            <div class="w-[104px]">
              <label class="field-label" for="minimum">Min score</label>
              <input
                id="minimum"
                name="minimum"
                type="number"
                min="0"
                max="100"
                [(ngModel)]="minimum"
                class="input tnum"
                placeholder="0"
              />
            </div>
            <div class="w-[140px]">
              <label class="field-label" for="intent">Intent</label>
              <select id="intent" name="intent" [(ngModel)]="intent" class="input">
                <option value="">All intents</option>
                @for (i of intents(); track i) {
                  <option [value]="i">{{ i }}</option>
                }
              </select>
            </div>
            <div class="w-[150px]">
              <label class="field-label" for="channel">Channel</label>
              <select id="channel" name="channel" [(ngModel)]="channel" class="input">
                <option value="">All channels</option>
                @for (c of channels; track c.key) {
                  <option [value]="c.key">{{ c.label }}</option>
                }
              </select>
            </div>
            <div class="w-[140px]">
              <label class="field-label" for="sort">Sort</label>
              <select id="sort" name="sort" [(ngModel)]="sort" class="input">
                <option value="score_desc">Highest score</option>
                <option value="score_asc">Lowest score</option>
              </select>
            </div>
            <button class="btn-secondary" type="submit" [disabled]="filtering()">
              @if (filtering()) {
                <app-icon name="spinner" [size]="14" /> Filtering…
              } @else {
                <app-icon name="filter" [size]="14" /> Apply
              }
            </button>
          </form>

          @if (filterError(); as problem) {
            <div class="p-4"><app-error [problem]="problem" (retry)="filter()" /></div>
          }

          @if (!opportunities().length) {
            <app-empty
              icon="target"
              title="No matching opportunities"
              text="Widen the filters, or open the trace if this run did not collect enough data to score."
            />
          } @else {
            <div class="overflow-x-auto">
              <table class="tbl tbl-interactive">
                <thead>
                  <tr>
                    <th class="w-12 text-right">#</th>
                    <th class="min-w-[240px]">Query</th>
                    <th class="w-[190px]">Opportunity</th>
                    <th class="min-w-[240px]">Why this gap exists</th>
                    <th class="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  @for (o of opportunities(); track o.id) {
                    <tr
                      tabindex="0"
                      (click)="selected.set(o)"
                      (keydown.enter)="selected.set(o)"
                      (keydown.space)="selected.set(o)"
                    >
                      <td class="tnum text-right text-ink-400">
                        {{ o.rank.toString().padStart(2, '0') }}
                      </td>
                      <td class="font-medium text-ink-950">{{ o.query_text }}</td>
                      <td><app-score-meter [score]="o.score" /></td>
                      <td class="text-label-xs leading-[16px] text-ink-600">
                        {{ o.explanation || 'No explanation was recorded for this gap.' }}
                      </td>
                      <td class="text-right text-ink-400">
                        <app-icon name="chevron-right" [size]="16" />
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
            <p
              class="flex items-center gap-1.5 border-t-hairline border-stroke-200 px-4 py-2.5 text-label-xs text-ink-400"
            >
              <app-icon name="info" [size]="12" /> Open any row for the full score breakdown. A
              higher score means a bigger winnable gap.
            </p>
          }
        </app-section>

        <!-- ========== Recommendations ========== -->
        <app-section
          title="Recommendations"
          [subtitle]="recommendations().length + ' content actions for the top opportunities'"
        >
          @if (actionError(); as problem) {
            <div class="p-4">
              <app-error [problem]="problem" (retry)="actionError.set(null)" />
            </div>
          }

          @if (!recommendations().length) {
            <app-empty
              icon="sparkles"
              title="No recommendations in this run"
              text="A run needs scored opportunities and a successful recommender stage before it can propose content."
            />
          } @else {
            <div class="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-4">
              @for (column of columns; track column.key) {
                <section class="flex min-w-0 flex-col gap-2.5">
                  <header
                    class="flex items-center justify-between gap-2 border-b-hairline border-stroke-200 pb-2"
                  >
                    <h3 class="flex items-center gap-1.5 text-label-sm font-semibold text-ink-950">
                      <app-icon [name]="column.icon" [size]="14" />
                      {{ column.label }}
                    </h3>
                    <span class="tnum badge-neutral">{{ byStatus(column.key).length }}</span>
                  </header>

                  @for (r of byStatus(column.key); track r.id) {
                    <article
                      class="rounded-8 border-hairline border-stroke-200 bg-surface-0 p-3 shadow-card transition-shadow duration-150 hover:shadow-raised"
                      [class.opacity-50]="updating().includes(r.id)"
                    >
                      <div class="mb-1.5 flex flex-wrap items-center gap-1.5">
                        <span class="badge-brand">{{ r.content_type.replaceAll('_', ' ') }}</span>
                        @if (r.priority) {
                          <span [class]="priorityCls(r.priority)">{{ r.priority }}</span>
                        }
                        @if (r.effort) {
                          <span class="badge-neutral">{{ r.effort }} effort</span>
                        }
                      </div>

                      <h4 class="text-label-sm font-semibold leading-[20px] text-ink-950">
                        {{ r.title }}
                      </h4>

                      @if (r.target_query) {
                        <p class="mt-1.5 flex items-center gap-1.5 text-label-xs text-ink-600">
                          <app-icon name="target" [size]="12" />
                          <span class="min-w-0 truncate">{{ r.target_query }}</span>
                        </p>
                      }

                      @if (r.rationale) {
                        <p class="mt-1.5 text-label-xs leading-[16px] text-ink-600">
                          {{ r.rationale }}
                        </p>
                      }

                      @if (r.outline?.length) {
                        <details class="group mt-2">
                          <summary
                            class="inline-flex cursor-pointer select-none items-center gap-1 text-label-xs font-medium text-ink-600 hover:text-ink-950"
                          >
                            <app-icon
                              name="chevron-right"
                              [size]="12"
                              class="transition-transform duration-150 group-open:rotate-90"
                            />
                            Outline
                          </summary>
                          <ol
                            class="mt-1.5 list-decimal space-y-0.5 pl-4 text-label-xs leading-[16px] text-ink-600"
                          >
                            @for (line of r.outline; track $index) {
                              <li>{{ line }}</li>
                            }
                          </ol>
                        </details>
                      }

                      <div
                        class="mt-2.5 flex flex-wrap items-center gap-1 border-t-hairline border-stroke-200 pt-2.5"
                      >
                        @for (c of columns; track c.key) {
                          @if (c.key !== r.status) {
                            <button
                              type="button"
                              class="btn-ghost btn-sm"
                              (click)="move(r, c.key)"
                              [disabled]="updating().includes(r.id)"
                              [attr.aria-label]="'Move ' + r.title + ' to ' + c.label"
                            >
                              <app-icon [name]="c.icon" [size]="11" /> {{ c.short }}
                            </button>
                          }
                        }
                      </div>
                    </article>
                  } @empty {
                    <p
                      class="rounded-8 border-hairline border-dashed border-stroke-300 px-3 py-6 text-center text-label-xs text-ink-400"
                    >
                      Nothing here
                    </p>
                  }
                </section>
              }
            </div>
          }
        </app-section>
      </div>
    }

    <!-- ========== Score breakdown drawer ========== -->
    @if (selected(); as o) {
      <div
        class="fixed inset-0 z-50 flex justify-end"
        role="dialog"
        aria-modal="true"
        aria-labelledby="score-title"
      >
        <button
          type="button"
          class="absolute inset-0 bg-ink-950/40 backdrop-blur-[2px]"
          (click)="selected.set(null)"
          aria-label="Close score breakdown"
        ></button>

        <div
          class="relative flex h-full w-full max-w-[460px] flex-col overflow-y-auto border-l-hairline border-stroke-200 bg-surface-0 shadow-drawer"
        >
          <header
            class="sticky top-0 z-10 flex items-start justify-between gap-3 border-b-hairline border-stroke-200 bg-surface-0/90 px-5 py-4 backdrop-blur-md"
          >
            <div class="min-w-0">
              <p class="eyebrow">Score breakdown &middot; rank {{ o.rank }}</p>
              <h2 id="score-title" class="mt-1 text-label-lg font-semibold text-ink-950">
                {{ o.query_text }}
              </h2>
            </div>
            <button
              type="button"
              class="btn-ghost btn-icon shrink-0"
              (click)="selected.set(null)"
              aria-label="Close"
            >
              <app-icon name="x" [size]="16" />
            </button>
          </header>

          <div class="space-y-5 px-5 py-5">
            <div class="flex items-end gap-3">
              <span class="tnum text-display-lg font-semibold leading-none text-ink-950">{{
                o.score | number: '1.1-1'
              }}</span>
              <span class="pb-1 text-label-sm text-ink-400">/ 100 opportunity</span>
            </div>

            @if (o.explanation) {
              <p
                class="rounded-8 border-hairline border-stroke-200 bg-surface-50 p-3 text-label-sm leading-[20px] text-ink-700"
              >
                {{ o.explanation }}
              </p>
            }

            <div>
              <h3 class="eyebrow mb-3">Components</h3>
              <ul class="space-y-3">
                @for (c of components(o); track c.key) {
                  <li>
                    <div class="flex items-baseline justify-between gap-2">
                      <span class="text-label-sm font-medium text-ink-950">{{ c.label }}</span>
                      <span class="tnum text-label-sm text-ink-700">{{ c.display }}</span>
                    </div>
                    @if (c.fraction !== null) {
                      <div class="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-surface-200">
                        <div
                          class="h-full rounded-full bg-brand-500"
                          [style.width.%]="c.fraction * 100"
                        ></div>
                      </div>
                    }
                    @if (c.what) {
                      <p class="mt-1 text-label-xs text-ink-400">{{ c.what }}</p>
                    }
                  </li>
                }
              </ul>
            </div>

            <div class="rounded-8 border-hairline border-stroke-200 bg-surface-50 p-3">
              <h3 class="text-label-sm font-semibold text-ink-950">How this is calculated</h3>
              <code
                class="tnum mt-2 block overflow-x-auto whitespace-nowrap rounded-6 border-hairline border-stroke-200 bg-surface-0 px-2.5 py-2 text-label-xs text-ink-700"
              >
                100 &times; demand &times; gap &times; (0.6 + 0.4 &times; contested) &times; (1
                &minus; 0.5 &times; difficulty)
              </code>
              <p class="mt-2 text-label-xs leading-[16px] text-ink-600">
                Every input comes from DataForSEO and is combined in Python. The language model
                never produces or adjusts a number &mdash; it only writes the explanation above.
              </p>
            </div>
          </div>
        </div>
      </div>
    }`,
})
export class ResultsPanel {
  readonly api = inject(ApiService);
  private readonly destroy = inject(DestroyRef);

  readonly runId = input.required<string>();

  readonly channels = CHANNELS;
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

  readonly columns: { key: RecommendationStatus; label: string; short: string; icon: IconName }[] =
    [
      { key: 'todo', label: 'To do', short: 'To do', icon: 'target' },
      { key: 'in_progress', label: 'In progress', short: 'Start', icon: 'play' },
      { key: 'done', label: 'Done', short: 'Done', icon: 'check' },
      { key: 'dismissed', label: 'Dismissed', short: 'Dismiss', icon: 'x' },
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

  constructor() {
    effect(() => {
      this.runId();
      this.load();
    });
  }

  /** Channel colour, read from the same tokens the charts use. */
  channelColor(index: number) {
    return `rgb(var(--chart-${(index % 4) + 1}))`;
  }

  channelLabel(key: string) {
    return CHANNELS.find((c) => c.key === key)?.label ?? key.replaceAll('_', ' ');
  }

  pillCls(value: string) {
    const base = 'rounded-6 px-2.5 py-1 text-label-xs font-medium transition-colors duration-150';
    return this.entity() === value
      ? `${base} bg-surface-0 text-ink-950 shadow-card`
      : `${base} text-ink-600 hover:text-ink-950`;
  }

  priorityCls(priority: string) {
    const p = priority.toLowerCase();
    if (p === 'high') return 'badge-danger';
    if (p === 'medium') return 'badge-warning';
    return 'badge-neutral';
  }

  cellTitle(q: VisibilityQuery, channel: string, state: number | null) {
    const who = this.entity() === 'brand' ? 'Your brand' : this.entity();
    if (state === null) return `${channel} was not measured for "${q.text}"`;
    return `${who} ${state ? 'is visible' : 'is absent'} on ${channel} for "${q.text}"`;
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

  /** 1 = visible, 0 = measured but absent, null = never measured. */
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
    const order = ['demand', 'gap', 'visibility', 'contested', 'difficulty', 'score'];
    return Object.entries(o.components)
      .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
      .map(([key, value]) => {
        const meta = COMPONENT_COPY[key];
        const numeric = typeof value === 'number' ? value : null;
        return {
          key,
          label: meta?.label ?? key.replaceAll('_', ' '),
          what: meta?.what ?? '',
          display: numeric === null ? JSON.stringify(value) : numeric.toFixed(4),
          // `score` is 0–100; every other component is a 0–1 ratio.
          fraction:
            numeric === null ? null : key === 'score' ? numeric / 100 : Math.min(1, numeric),
        };
      });
  }
}
