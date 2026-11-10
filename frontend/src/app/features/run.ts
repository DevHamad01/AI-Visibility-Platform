import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription, timer } from 'rxjs';
import { ApiService } from '../core/api.service';
import { problemOf } from '../core/errors';
import { Problem, Run, Stage } from '../core/models';
import { Icon, IconName } from '../shared/icon';
import {
  ErrorState,
  PageHeader,
  PartialBanner,
  Section,
  Skeleton,
  Stat,
  StatusBadge,
} from '../shared/ui';
import { ResultsPanel } from './results';

/** Pipeline order, so the trace reads top-to-bottom like the DAG. */
const STAGES = [
  'query_planner',
  'keyword_retrieval',
  'serp_retrieval',
  'llm_mentions_retrieval',
  'normalizer',
  'opportunity_scorer',
  'gap_analyst',
  'recommender',
  'report',
];

/** Plain-language purpose per stage — the trace should teach, not just log. */
const STAGE_COPY: Record<string, { label: string; what: string; icon: IconName }> = {
  query_planner: {
    label: 'Query planner',
    what: 'Chooses which searches to measure and which data tools to call',
    icon: 'sparkles',
  },
  keyword_retrieval: {
    label: 'Keyword retrieval',
    what: 'Pulls search volume, competition and difficulty',
    icon: 'search',
  },
  serp_retrieval: {
    label: 'SERP retrieval',
    what: 'Reads Google results, AI Overviews and related questions',
    icon: 'globe',
  },
  llm_mentions_retrieval: {
    label: 'LLM mentions',
    what: 'Checks what AI assistants say about you and your rivals',
    icon: 'activity',
  },
  normalizer: {
    label: 'Normalizer',
    what: 'Turns raw provider JSON into typed queries and observations',
    icon: 'layers',
  },
  opportunity_scorer: {
    label: 'Opportunity scorer',
    what: 'Scores every gap deterministically in Python',
    icon: 'target',
  },
  gap_analyst: {
    label: 'Gap analyst',
    what: 'Classifies intent and explains why each gap exists',
    icon: 'eye',
  },
  recommender: {
    label: 'Recommender',
    what: 'Drafts the content that would close the top gaps',
    icon: 'check-circle',
  },
  report: {
    label: 'Report',
    what: 'Assembles the final result and decides the run status',
    icon: 'bar-chart',
  },
};

@Component({
  imports: [
    RouterLink,
    DatePipe,
    DecimalPipe,
    Icon,
    ErrorState,
    PageHeader,
    PartialBanner,
    Section,
    Skeleton,
    Stat,
    StatusBadge,
    ResultsPanel,
  ],
  template: `@if (loading()) {
      <app-skeleton variant="stats" />
      <div class="mt-6"><app-skeleton variant="card" /></div>
    } @else if (error(); as problem) {
      <app-error [problem]="problem" (retry)="load()" />
    } @else if (run(); as r) {
      <a
        [routerLink]="['/brands', r.brand_id]"
        class="mb-5 inline-flex items-center gap-1.5 text-label-sm font-medium text-ink-600 transition-colors duration-150 hover:text-ink-950"
      >
        <app-icon name="arrow-left" [size]="14" /> Brand workspace
      </a>

      <app-page-header
        [eyebrow]="'Analysis · ' + (r.created_at | date: 'MMM d, y · HH:mm')"
        [title]="headline()"
        [subtitle]="subhead()"
      >
        <app-status-badge [status]="r.status" />
        @if (!active()) {
          <button class="btn-primary" (click)="rerun()" [disabled]="starting()">
            @if (starting()) {
              <app-icon name="spinner" [size]="14" /> Starting…
            } @else {
              <app-icon name="refresh" [size]="14" /> Run again
            }
          </button>
        }
      </app-page-header>

      @if (startError(); as problem) {
        <div class="mb-4"><app-error [problem]="problem" (retry)="rerun()" /></div>
      }

      @if (r.status === 'partial' || r.status === 'failed') {
        <div class="mb-4">
          <app-partial-banner
            [title]="
              r.status === 'partial'
                ? 'Some data could not be collected'
                : 'This analysis could not produce a result'
            "
            [text]="failureSummary()"
            [stages]="failedStages()"
          >
            <p class="mt-2.5 text-label-xs text-ink-400">
              Work from the stages that did succeed is kept — nothing already collected was thrown
              away.
            </p>
          </app-partial-banner>
        </div>
      }

      @if (connection()) {
        <div
          class="card mb-4 flex items-start gap-2.5 p-3"
          style="background: rgb(var(--warning-500) / 0.05)"
          role="status"
        >
          <span class="mt-0.5 text-warning-700"><app-icon name="info" [size]="14" /></span>
          <p class="text-label-sm text-ink-700">{{ connection() }}</p>
        </div>
      }

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="card p-4">
          <app-stat label="Queries" [value]="r.metrics['queries'] ?? '—'" detail="measured" />
        </div>
        <div class="card p-4">
          <app-stat
            label="Opportunities"
            [value]="r.metrics['opportunities'] ?? '—'"
            detail="scored gaps"
          />
        </div>
        <div class="card p-4">
          <app-stat label="Elapsed" [value]="elapsed()" [detail]="active() ? 'running' : 'total'" />
        </div>
        <div class="card p-4">
          <app-stat
            label="Data cost"
            [value]="'$' + (r.dataforseo_cost_usd | number: '1.4-4')"
            detail="DataForSEO spend"
          />
        </div>
      </div>

      <!-- Tabs -->
      <div
        class="mt-6 inline-flex items-center gap-1 rounded-8 border-hairline border-stroke-200 bg-surface-50 p-1"
        role="tablist"
        aria-label="Analysis sections"
      >
        <button
          role="tab"
          [attr.aria-selected]="tab() === 'results'"
          (click)="tab.set('results')"
          class="inline-flex items-center gap-1.5 rounded-6 px-3 py-1.5 text-label-sm font-medium transition-colors duration-150"
          [class]="
            tab() === 'results'
              ? 'bg-surface-0 text-ink-950 shadow-card'
              : 'text-ink-600 hover:text-ink-950'
          "
        >
          <app-icon name="bar-chart" [size]="14" /> Results
        </button>
        <button
          role="tab"
          [attr.aria-selected]="tab() === 'trace'"
          (click)="tab.set('trace')"
          class="inline-flex items-center gap-1.5 rounded-6 px-3 py-1.5 text-label-sm font-medium transition-colors duration-150"
          [class]="
            tab() === 'trace'
              ? 'bg-surface-0 text-ink-950 shadow-card'
              : 'text-ink-600 hover:text-ink-950'
          "
        >
          <app-icon name="layers" [size]="14" /> Trace
          <span class="tnum badge-neutral">{{ completed() }}/{{ total() }}</span>
        </button>
      </div>

      <div class="mt-4">
        @if (tab() === 'trace' || active()) {
          <div class="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
            <app-section title="Pipeline" subtitle="Nine single-responsibility stages">
              <div toolbar>
                @if (active()) {
                  <span class="badge-brand">
                    <span class="relative flex h-1.5 w-1.5">
                      <span
                        class="absolute inset-0 animate-pulse-ring rounded-full bg-brand-500"
                      ></span>
                      <span class="relative h-1.5 w-1.5 rounded-full bg-brand-500"></span>
                    </span>
                    Live
                  </span>
                }
              </div>

              <div class="border-b-hairline border-stroke-200 px-4 py-3">
                <div class="h-1 w-full overflow-hidden rounded-full bg-surface-200">
                  <div
                    class="h-full rounded-full bg-brand-500 transition-[width] duration-150"
                    [style.width.%]="(100 * completed()) / total()"
                  ></div>
                </div>
                <p class="mt-2 text-label-xs text-ink-400">
                  {{ completed() }} of {{ total() }} stages finished ·
                  {{ active() ? 'collecting and processing' : 'analysis ended' }}
                </p>
              </div>

              <ol class="p-4">
                @for (
                  stage of orderedStages();
                  track stage.stage;
                  let i = $index;
                  let last = $last
                ) {
                  <li class="relative flex gap-3 pb-4" [class.pb-0]="last">
                    @if (!last) {
                      <span
                        class="absolute left-[13px] top-7 h-[calc(100%-18px)] w-px bg-stroke-200"
                        aria-hidden="true"
                      ></span>
                    }

                    <span
                      class="relative z-10 mt-0.5 grid h-[27px] w-[27px] shrink-0 place-items-center rounded-full border-hairline"
                      [class]="nodeCls(stage.status)"
                    >
                      @if (stage.status === 'succeeded') {
                        <app-icon name="check" [size]="13" />
                      } @else if (stage.status === 'failed') {
                        <app-icon name="x" [size]="13" />
                      } @else if (stage.status === 'running') {
                        <app-icon name="spinner" [size]="13" />
                      } @else {
                        <span class="tnum text-label-xs font-semibold">{{ i + 1 }}</span>
                      }
                    </span>

                    <div class="min-w-0 flex-1">
                      <div class="flex flex-wrap items-center gap-2">
                        <h3 class="text-label-sm font-semibold text-ink-950">
                          {{ copy(stage.stage).label }}
                        </h3>
                        <app-status-badge [status]="stage.status" />
                        @if (stage.duration_ms !== null) {
                          <span class="tnum text-label-xs text-ink-400"
                            >{{ stage.duration_ms }} ms</span
                          >
                        }
                        @if (stage.attempts > 1) {
                          <span class="badge-warning">{{ stage.attempts }} attempts</span>
                        }
                      </div>

                      <p class="mt-0.5 text-label-xs leading-[16px] text-ink-600">
                        {{ copy(stage.stage).what }}
                      </p>

                      @if (stage.error_message) {
                        <p
                          class="mt-2 rounded-6 px-2 py-1.5 text-label-xs leading-[16px] text-danger-700"
                          style="background: rgb(var(--danger-500) / 0.08)"
                        >
                          <span class="font-semibold">{{ stage.error_type }}</span>
                          · {{ stage.error_message }}
                        </p>
                      }

                      @if (stage.output_summary; as output) {
                        <details class="group mt-2">
                          <summary
                            class="inline-flex cursor-pointer select-none items-center gap-1 text-label-xs font-medium text-ink-600 transition-colors duration-150 hover:text-ink-950"
                          >
                            <app-icon
                              name="chevron-right"
                              [size]="12"
                              class="transition-transform duration-150 group-open:rotate-90"
                            />
                            {{ provider(output) }}
                          </summary>
                          <pre
                            class="tnum mt-2 overflow-x-auto rounded-6 border-hairline border-stroke-200 bg-surface-50 p-2.5 text-label-xs leading-[16px] text-ink-700"
                            >{{ stringify(output) }}</pre>
                        </details>
                      }
                    </div>
                  </li>
                }
              </ol>
            </app-section>

            <div class="space-y-4">
              <app-section title="Run details">
                <dl class="divide-y-hairline divide-stroke-200">
                  <div class="flex items-center justify-between gap-3 px-4 py-2.5">
                    <dt class="text-label-sm text-ink-600">LLM provider</dt>
                    <dd class="text-label-sm font-medium text-ink-950">
                      {{ r.llm_provider || 'Not recorded' }}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-3 px-4 py-2.5">
                    <dt class="text-label-sm text-ink-600">Model</dt>
                    <dd class="tnum truncate text-label-sm font-medium text-ink-950">
                      {{ r.llm_model || '—' }}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-3 px-4 py-2.5">
                    <dt class="text-label-sm text-ink-600">Started</dt>
                    <dd class="tnum text-label-sm font-medium text-ink-950">
                      {{ r.started_at ? (r.started_at | date: 'HH:mm:ss') : 'Queued' }}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-3 px-4 py-2.5">
                    <dt class="text-label-sm text-ink-600">Finished</dt>
                    <dd class="tnum text-label-sm font-medium text-ink-950">
                      {{ r.finished_at ? (r.finished_at | date: 'HH:mm:ss') : '—' }}
                    </dd>
                  </div>
                  <div class="px-4 py-3">
                    <dt class="eyebrow">Trace ID</dt>
                    <dd class="mt-1.5 flex items-center gap-2">
                      <code
                        class="tnum min-w-0 flex-1 truncate rounded-6 border-hairline border-stroke-200 bg-surface-50 px-2 py-1 text-label-xs text-ink-700"
                        >{{ r.trace_id || r.id }}</code
                      >
                      <button
                        class="btn-secondary btn-sm shrink-0"
                        (click)="copyTrace()"
                        [attr.aria-label]="'Copy trace ID'"
                      >
                        <app-icon [name]="copied() ? 'check' : 'layers'" [size]="12" />
                        {{ copied() ? 'Copied' : 'Copy' }}
                      </button>
                    </dd>
                    <p class="mt-2 text-label-xs leading-[16px] text-ink-400">
                      Quote this id to find every log line for this run.
                    </p>
                  </div>
                </dl>
              </app-section>

              <div class="card p-4">
                <p class="flex items-center gap-1.5 text-label-sm font-semibold text-ink-950">
                  <app-icon name="info" [size]="14" /> Why failures stay visible
                </p>
                <p class="mt-1.5 text-label-xs leading-[16px] text-ink-600">
                  Each stage records its own outcome. A failed dependency never discards the work
                  other branches already finished — that is what makes a run
                  <span class="font-medium text-ink-700">partial</span> instead of lost.
                </p>
              </div>
            </div>
          </div>
        }

        @if (tab() === 'results' && !active()) {
          <app-results [runId]="r.id" />
        }
      </div>
    }`,
})
export class RunPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroy = inject(DestroyRef);

  readonly run = signal<Run | null>(null);
  readonly loading = signal(true);
  readonly error = signal<Problem | null>(null);
  readonly startError = signal<Problem | null>(null);
  readonly connection = signal('');
  readonly starting = signal(false);
  readonly copied = signal(false);
  readonly tab = signal<'results' | 'trace'>('results');
  readonly now = signal(Date.now());

  readonly active = computed(
    () => !!this.run() && ['queued', 'running'].includes(this.run()!.status),
  );
  readonly total = computed(() => this.run()?.stages.length || STAGES.length);
  readonly completed = computed(
    () =>
      this.run()?.stages.filter((s) => ['succeeded', 'failed', 'skipped'].includes(s.status))
        .length || 0,
  );
  readonly orderedStages = computed(() =>
    [...(this.run()?.stages || [])].sort(
      (a, b) => STAGES.indexOf(a.stage) - STAGES.indexOf(b.stage),
    ),
  );
  readonly failedStages = computed(() =>
    this.orderedStages()
      .filter((s) => s.status === 'failed')
      .map((s) => ({
        stage: this.copy(s.stage).label,
        reason: this.stageReason(s),
      })),
  );

  readonly headline = computed(() => {
    const status = this.run()?.status;
    if (this.active()) return 'Analysis in progress';
    if (status === 'failed') return 'Analysis needs attention';
    if (status === 'partial') return 'Partial results';
    return 'Analysis results';
  });
  readonly subhead = computed(() =>
    this.active()
      ? 'Each stage reports as it finishes — nothing is hidden while the run is in flight.'
      : 'Evidence, scored gaps, and the content that would close them.',
  );

  /** Turns the backend's raw error summary into something a human can act on. */
  readonly failureSummary = computed(() => {
    const message = this.run()?.error_summary || '';
    if (/40104|verify your account/i.test(message))
      return 'DataForSEO needs the connected account verified before it will return search data. Verify the account, then run the analysis again.';
    if (/budget/i.test(message))
      return 'The run hit its per-run spending cap before every call completed. Raise DATAFORSEO_MAX_COST_PER_RUN or reduce the query count, then run again.';
    if (/circuit/i.test(message))
      return 'A dependency failed repeatedly, so its circuit breaker opened and remaining calls failed fast instead of hanging.';
    return 'One or more stages could not finish. The trace below records the exact reason for each.';
  });

  readonly elapsed = computed(() => {
    const r = this.run();
    if (!r?.started_at) return '—';
    const end = r.finished_at ? new Date(r.finished_at).getTime() : this.now();
    const seconds = Math.max(0, Math.floor((end - new Date(r.started_at).getTime()) / 1000));
    return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`;
  });

  private id = '';
  private stream?: Subscription;
  private poll?: Subscription;
  private key = crypto.randomUUID();

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      this.id = params.get('id')!;
      this.load();
    });
    timer(0, 1000)
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.now.set(Date.now()));
    this.destroy.onDestroy(() => {
      this.stream?.unsubscribe();
      this.poll?.unsubscribe();
    });
  }

  copy(stage: string) {
    return (
      STAGE_COPY[stage] ?? {
        label: stage.replaceAll('_', ' '),
        what: 'Pipeline stage',
        icon: 'layers' as IconName,
      }
    );
  }

  nodeCls(status: string) {
    switch (status) {
      case 'succeeded':
        return 'border-transparent bg-success-500 text-white';
      case 'failed':
        return 'border-transparent bg-danger-500 text-white';
      case 'running':
        return 'border-transparent bg-brand-500 text-white';
      case 'skipped':
        return 'border-stroke-200 bg-surface-100 text-ink-400';
      default:
        return 'border-stroke-200 bg-surface-0 text-ink-400';
    }
  }

  private stageReason(stage: Stage): string {
    const message = stage.error_message || '';
    if (/40104|verify your account/i.test(message)) return 'DataForSEO account is not verified yet';
    if (/budget/i.test(message)) return 'Hit the per-run spending cap';
    if (/circuit/i.test(message)) return 'Circuit breaker was open — failed fast';
    if (/timeout|timed out/i.test(message)) return 'The provider did not respond in time';
    return message.slice(0, 160) || 'No reason recorded';
  }

  load() {
    this.stream?.unsubscribe();
    this.poll?.unsubscribe();
    this.loading.set(true);
    this.error.set(null);
    this.run.set(null);
    this.connection.set('');
    this.api
      .run(this.id)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (r) => {
          this.run.set(r);
          this.loading.set(false);
          if (this.active()) {
            this.tab.set('trace');
            this.connect();
          } else this.tab.set('results');
        },
        error: (e) => {
          this.error.set(problemOf(e));
          this.loading.set(false);
        },
      });
  }

  private connect() {
    this.stream = this.api
      .events(this.id)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (event) => {
          if (event.status)
            this.run.update((r) =>
              r
                ? {
                    ...r,
                    status: event.status!,
                    progress: event.progress || r.progress,
                    stages: r.stages.map((s) => ({
                      ...s,
                      ...event.stages?.find((u) => u.stage === s.stage),
                    })),
                  }
                : r,
            );
          if (event.status && !['queued', 'running'].includes(event.status)) this.refresh();
        },
        error: () => {
          // SSE dropped (proxy timeout, sleep/resume). Fall back to polling
          // rather than leaving the page frozen on a stale snapshot.
          this.connection.set(
            'Live updates were interrupted, so the status is being refreshed every five seconds instead.',
          );
          this.poll = timer(0, 5000)
            .pipe(takeUntilDestroyed(this.destroy))
            .subscribe(() => this.refresh());
        },
      });
  }

  private refresh() {
    this.api
      .run(this.id)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (r) => {
          this.run.set(r);
          if (!this.active()) {
            this.poll?.unsubscribe();
            this.stream?.unsubscribe();
            this.connection.set('');
          }
        },
        error: (e) =>
          this.connection.set(problemOf(e).detail || 'Could not refresh this analysis.'),
      });
  }

  provider(output: Record<string, unknown>) {
    return output['provider']
      ? `Served by ${output['provider']}:${output['model']}`
      : 'Stage output';
  }

  stringify(value: unknown) {
    return JSON.stringify(value, null, 2);
  }

  copyTrace() {
    void navigator.clipboard.writeText(this.run()?.trace_id || this.id).then(
      () => this.copied.set(true),
      () =>
        this.connection.set(
          'Could not copy automatically — select the trace id above and copy it.',
        ),
    );
  }

  rerun() {
    if (this.starting()) return;
    const r = this.run();
    if (!r) return;
    this.starting.set(true);
    this.startError.set(null);
    this.api.startRun(r.brand_id, this.key).subscribe({
      next: (run) => {
        this.starting.set(false);
        this.key = crypto.randomUUID();
        void this.router.navigate(['/runs', run.id]);
      },
      error: (e) => {
        this.starting.set(false);
        this.startError.set(problemOf(e));
      },
    });
  }
}
