import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription, timer } from 'rxjs';
import { ApiService } from '../core/api.service';
import { Problem, Run } from '../core/models';
import { problemOf } from '../core/errors';
import { Badge, ErrorState, Loading, Stat } from '../shared/ui';
import { ResultsPanel } from './results';
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
@Component({
  imports: [RouterLink, DatePipe, DecimalPipe, Badge, ErrorState, Loading, Stat, ResultsPanel],
  template: ` @if (loading()) {
      <app-loading />
    } @else if (error(); as p) {
      <app-error [problem]="p" (retry)="load()" />
    } @else if (run(); as r) {
      <a class="back-link" [routerLink]="['/brands', r.brand_id]">← Brand workspace</a>
      <div class="page-head">
        <div>
          <span class="eyebrow">Analysis · {{ r.created_at | date: 'MMM d, y · HH:mm' }}</span>
          <h1>
            {{
              active()
                ? 'Finding your next opportunity'
                : r.status === 'failed'
                  ? 'Analysis needs attention'
                  : 'Your visibility, unpacked'
            }}
          </h1>
          <p>
            {{
              active()
                ? 'Follow every stage as your analysis moves from questions to recommendations.'
                : 'Explore the evidence, understand the gaps and decide what to do next.'
            }}
          </p>
        </div>
        <div class="actions">
          <app-badge [status]="r.status" />
          @if (!active()) {
            <button class="btn primary" (click)="rerun()" [disabled]="starting()">
              {{ starting() ? 'Starting…' : '↗ Run again' }}
            </button>
          }
        </div>
      </div>
      @if (startError(); as p) {
        <app-error [problem]="p" (retry)="rerun()" />
      }
      @if (r.status === 'failed' || r.status === 'partial') {
        <section class="notice" [class.danger]="r.status === 'failed'" role="status">
          <strong>{{
            r.status === 'partial'
              ? 'Some data could not be collected'
              : 'This analysis could not produce a complete result'
          }}</strong>
          <p>{{ failureSummary() }}</p>
          <p>Available results are preserved. Resolve the dependency issue before running again.</p>
        </section>
      }
      @if (connection()) {
        <div class="notice">
          <strong>Live connection update</strong>
          <p>{{ connection() }}</p>
        </div>
      }
      <div class="stats">
        <app-stat
          label="Queries"
          [value]="r.metrics['queries'] ?? '—'"
          detail="Discovered this run"
        /><app-stat
          label="Opportunities"
          [value]="r.metrics['opportunities'] ?? '—'"
          detail="Scored visibility gaps"
        /><app-stat label="Elapsed" [value]="elapsed()" detail="Wall-clock duration" /><app-stat
          label="Data cost"
          [value]="'$' + (r.dataforseo_cost_usd | number: '1.4-4')"
          detail="DataForSEO spend"
        />
      </div>
      <div class="tabs" role="tablist" aria-label="Analysis sections">
        <button
          role="tab"
          [attr.aria-selected]="tab() === 'results'"
          [class.active]="tab() === 'results'"
          (click)="tab.set('results')"
        >
          Results & recommendations</button
        ><button
          role="tab"
          [attr.aria-selected]="tab() === 'trace'"
          [class.active]="tab() === 'trace'"
          (click)="tab.set('trace')"
        >
          Stage trace · {{ completed() }}/{{ r.stages.length || 9 }}
        </button>
      </div>
      @if (tab() === 'trace' || active()) {
        <div class="split">
          <section class="card">
            <div class="section-head" style="margin-top:0">
              <div>
                <h2>Analysis pipeline</h2>
                <p>Nine focused stages. One transparent analysis.</p>
              </div>
              @if (active()) {
                <span class="live-pulse"><span class="status-dot"></span>Live</span>
              }
            </div>
            <div class="progress-track">
              <span [style.width.%]="(100 * completed()) / (r.stages.length || 9)"></span>
            </div>
            <p class="muted small-text">
              {{ completed() }} stages finished ·
              {{ active() ? 'Collecting and processing data' : 'Analysis ended' }}
            </p>
            <ol class="timeline">
              @for (stage of orderedStages(); track stage.stage; let i = $index) {
                <li>
                  <span class="stage-number">{{ stage.status === 'succeeded' ? '✓' : i + 1 }}</span>
                  <div class="stage-body">
                    <strong>{{ stage.stage.replaceAll('_', ' ') }}</strong>
                    <p>
                      {{ stage.attempts }} attempt(s) ·
                      {{ stage.duration_ms === null ? 'Not timed yet' : stage.duration_ms + ' ms' }}
                    </p>
                    @if (stage.error_message) {
                      <p class="absent">{{ stage.error_message }}</p>
                    }
                    @if (stage.output_summary; as output) {
                      <details>
                        <summary>Stage output · {{ provider(output) }}</summary>
                        <pre>{{ stringify(output) }}</pre>
                      </details>
                    }
                  </div>
                  <app-badge [status]="stage.status" />
                </li>
              }
            </ol>
          </section>
          <aside>
            <section class="card">
              <h2>Run details</h2>
              <div class="info-row">
                <span>Provider</span><strong>{{ r.llm_provider || 'Not recorded yet' }}</strong>
              </div>
              <div class="info-row">
                <span>Model</span><strong class="mono">{{ r.llm_model || '—' }}</strong>
              </div>
              <div class="info-row">
                <span>Started</span
                ><strong>{{ r.started_at ? (r.started_at | date: 'HH:mm:ss') : 'Queued' }}</strong>
              </div>
              <div class="info-row">
                <span>Finished</span
                ><strong>{{ r.finished_at ? (r.finished_at | date: 'HH:mm:ss') : '—' }}</strong>
              </div>
              <p class="eyebrow" style="margin-top:24px">Trace ID</p>
              <p class="mono">{{ r.trace_id || r.id }}</p>
              <button class="btn small" (click)="copyTrace()">
                {{ copied() ? 'Copied ✓' : 'Copy trace ID' }}
              </button>
            </section>
            <div class="notice">
              <strong>Failures remain visible</strong>
              <p>
                A dependency failure is recorded per stage. Successful branches keep their work so
                partial results remain useful.
              </p>
            </div>
          </aside>
        </div>
      }
      @if (tab() === 'results' && !active()) {
        <app-results [runId]="r.id" [status]="r.status" />
      }
    }`,
})
export class RunPage {
  readonly failureSummary = computed(() => {
    const message = this.run()?.error_summary || '';
    if (/40104|verify your account/i.test(message))
      return 'DataForSEO requires account verification before it can collect search data. Verify the connected account, then run the analysis again.';
    if (/budget/i.test(message))
      return 'Some requested data exceeded the per-run spending limit. Review the budget or reduce the query count before trying again.';
    return 'One or more analysis stages could not finish. Open the stage trace for the recorded reason and available results.';
  });
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
  readonly elapsed = computed(() => {
    const r = this.run();
    if (!r?.started_at) return '—';
    const seconds = Math.max(
      0,
      Math.floor(
        ((r.finished_at ? new Date(r.finished_at).getTime() : this.now()) -
          new Date(r.started_at).getTime()) /
          1000,
      ),
    );
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
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
          this.connection.set(
            'Live updates were interrupted. Run status is refreshed every five seconds.',
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
    return output['provider'] ? `${output['provider']}:${output['model']}` : 'Recorded details';
  }
  stringify(value: unknown) {
    return JSON.stringify(value, null, 2);
  }
  copyTrace() {
    void navigator.clipboard.writeText(this.run()?.trace_id || this.id).then(
      () => this.copied.set(true),
      () =>
        this.connection.set(
          'Could not copy automatically. Select and copy the trace ID shown above.',
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
