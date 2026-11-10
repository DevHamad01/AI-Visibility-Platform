import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { problemOf } from '../core/errors';
import { Comparison, OpportunityDelta, Problem, RunSummary } from '../core/models';
import { Icon, IconName } from '../shared/icon';
import { Empty, ErrorState, PageHeader, Section, Skeleton, Stat } from '../shared/ui';

/**
 * How each change reads. `improved` means the remaining gap got *smaller*,
 * so a negative delta is the good direction — the UI must not show it as a
 * loss.
 */
const CHANGE_COPY: Record<
  OpportunityDelta['change'],
  { label: string; icon: IconName; cls: string; tone: string }
> = {
  improved: {
    label: 'Improved',
    icon: 'trending-down',
    cls: 'badge-success',
    tone: 'text-success-700',
  },
  declined: {
    label: 'Declined',
    icon: 'trending-up',
    cls: 'badge-danger',
    tone: 'text-danger-700',
  },
  new: { label: 'New gap', icon: 'plus', cls: 'badge-warning', tone: 'text-warning-700' },
  dropped: { label: 'Resolved', icon: 'check', cls: 'badge-success', tone: 'text-success-700' },
  unchanged: { label: 'Unchanged', icon: 'minus', cls: 'badge-neutral', tone: 'text-ink-400' },
};

@Component({
  imports: [
    RouterLink,
    FormsModule,
    DecimalPipe,
    Icon,
    Empty,
    ErrorState,
    PageHeader,
    Section,
    Skeleton,
    Stat,
  ],
  template: `<a
      [routerLink]="['/brands', id]"
      class="mb-5 inline-flex items-center gap-1.5 text-label-sm font-medium text-ink-600 transition-colors duration-150 hover:text-ink-950"
    >
      <app-icon name="arrow-left" [size]="14" /> Brand workspace
    </a>

    <app-page-header
      eyebrow="Measure the change"
      title="Compare analyses"
      subtitle="See which visibility gaps shrank, grew, appeared or were closed between two runs."
    />

    @if (error(); as problem) {
      <app-error [problem]="problem" (retry)="load()" />
    } @else if (loading()) {
      <app-skeleton variant="table" />
    } @else if (runs().length < 2) {
      <div class="card">
        <app-empty
          icon="compare"
          title="Two analyses tell a better story"
          text="Complete at least two analyses for this brand, then come back to see what moved between them."
        >
          <a class="btn-primary" [routerLink]="['/brands', id]">
            <app-icon name="arrow-left" [size]="14" /> Back to the brand
          </a>
        </app-empty>
      </div>
    } @else {
      <app-section title="Pick two runs" subtitle="Baseline first, then what you want to measure">
        <form class="flex flex-wrap items-end gap-3 p-4" (ngSubmit)="compare()">
          <div class="min-w-[220px] flex-1">
            <label class="field-label" for="base">Baseline</label>
            <select
              id="base"
              name="base"
              class="input"
              [(ngModel)]="base"
              (ngModelChange)="result.set(null)"
            >
              @for (run of runs(); track run.id) {
                <option [value]="run.id">{{ runLabel(run) }}</option>
              }
            </select>
          </div>

          <span
            class="mb-2 hidden h-9 w-9 shrink-0 place-items-center rounded-full border-hairline border-stroke-200 bg-surface-50 text-ink-400 sm:grid"
            aria-hidden="true"
          >
            <app-icon name="arrow-right" [size]="16" />
          </span>

          <div class="min-w-[220px] flex-1">
            <label class="field-label" for="target">Target</label>
            <select
              id="target"
              name="target"
              class="input"
              [(ngModel)]="target"
              (ngModelChange)="result.set(null)"
            >
              @for (run of runs(); track run.id) {
                <option [value]="run.id">{{ runLabel(run) }}</option>
              }
            </select>
          </div>

          <button class="btn-primary" type="submit" [disabled]="base === target || comparing()">
            @if (comparing()) {
              <app-icon name="spinner" [size]="14" /> Comparing…
            } @else {
              <app-icon name="compare" [size]="14" /> Compare
            }
          </button>
        </form>

        @if (base === target) {
          <p class="field-error px-4 pb-4">Pick two different runs to compare.</p>
        } @else {
          <p
            class="flex items-start gap-1.5 border-t-hairline border-stroke-200 px-4 py-2.5 text-label-xs leading-[16px] text-ink-400"
          >
            <app-icon name="info" [size]="12" class="mt-0.5 shrink-0" />
            A lower opportunity score means a smaller remaining gap, so "improved" shows as a
            negative change. Scores also move with demand, difficulty and competitor presence — they
            do not isolate your visibility alone.
          </p>
        }
      </app-section>

      @if (compareError(); as problem) {
        <div class="mt-4"><app-error [problem]="problem" (retry)="compare()" /></div>
      }

      @if (result(); as data) {
        @if (!data.deltas.length) {
          <div class="card mt-4">
            <app-empty
              icon="target"
              title="No scored queries in common"
              text="Neither run stored opportunity scores. Open each run's trace to see whether data collection succeeded."
            />
          </div>
        } @else {
          <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div class="card p-4">
              <app-stat
                label="Improved"
                [value]="count('improved') + count('dropped')"
                detail="gaps smaller or closed"
              />
            </div>
            <div class="card p-4">
              <app-stat label="Declined" [value]="count('declined')" detail="gaps grew wider" />
            </div>
            <div class="card p-4">
              <app-stat label="New gaps" [value]="count('new')" detail="not scored before" />
            </div>
            <div class="card p-4">
              <app-stat label="Net change" [value]="netChange()" detail="sum of score movement" />
            </div>
          </div>

          <div class="mt-4">
            <app-section
              title="Query by query"
              [subtitle]="data.deltas.length + ' queries, biggest movement first'"
            >
              <div class="overflow-x-auto">
                <table class="tbl">
                  <thead>
                    <tr>
                      <th class="min-w-[260px]">Search query</th>
                      <th class="w-[110px] text-right">Baseline</th>
                      <th class="w-[110px] text-right">Target</th>
                      <th class="w-[150px]">Change</th>
                      <th class="w-[130px]">Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (d of sorted(); track d.query_text) {
                      <tr>
                        <td class="font-medium text-ink-950">{{ d.query_text }}</td>
                        <td class="tnum text-right text-ink-600">
                          @if (d.base_score === null) {
                            <span class="text-ink-400">&mdash;</span>
                          } @else {
                            {{ d.base_score | number: '1.1-1' }}
                          }
                        </td>
                        <td class="tnum text-right font-medium text-ink-950">
                          @if (d.target_score === null) {
                            <span class="text-ink-400">&mdash;</span>
                          } @else {
                            {{ d.target_score | number: '1.1-1' }}
                          }
                        </td>
                        <td>
                          @if (d.delta === null) {
                            <span class="text-ink-400">&mdash;</span>
                          } @else {
                            <span
                              class="tnum inline-flex items-center gap-1 text-label-sm font-medium"
                              [class]="copy(d.change).tone"
                            >
                              <app-icon [name]="copy(d.change).icon" [size]="12" />
                              {{ d.delta > 0 ? '+' : '' }}{{ d.delta | number: '1.1-1' }}
                            </span>
                          }
                        </td>
                        <td>
                          <span [class]="copy(d.change).cls">{{ copy(d.change).label }}</span>
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            </app-section>
          </div>
        }
      }
    }`,
})
export class ComparePage {
  private readonly api = inject(ApiService);

  readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly runs = signal<RunSummary[]>([]);
  readonly loading = signal(true);
  readonly comparing = signal(false);
  readonly error = signal<Problem | null>(null);
  readonly compareError = signal<Problem | null>(null);
  readonly result = signal<Comparison | null>(null);

  base = '';
  target = '';

  /** Biggest absolute movement first; unscored rows sink to the bottom. */
  readonly sorted = computed(() =>
    [...(this.result()?.deltas ?? [])].sort(
      (a, b) => Math.abs(b.delta ?? -1) - Math.abs(a.delta ?? -1),
    ),
  );

  readonly netChange = computed(() => {
    const deltas = this.result()?.deltas ?? [];
    const sum = deltas.reduce((total, d) => total + (d.delta ?? 0), 0);
    return `${sum > 0 ? '+' : ''}${sum.toFixed(1)}`;
  });

  constructor() {
    this.load();
  }

  copy(change: OpportunityDelta['change']) {
    return CHANGE_COPY[change] ?? CHANGE_COPY.unchanged;
  }

  count(change: OpportunityDelta['change']) {
    return (this.result()?.deltas ?? []).filter((d) => d.change === change).length;
  }

  runLabel(run: RunSummary) {
    const when = new Date(run.created_at).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
    return `${when} · ${run.status} · ${run.id.slice(0, 8)}`;
  }

  load() {
    this.error.set(null);
    this.loading.set(true);
    this.api.runs(this.id).subscribe({
      next: (p) => {
        this.runs.set(p.items);
        // Newest is the natural target; the one before it is the baseline.
        this.target = p.items[0]?.id || '';
        this.base = p.items[1]?.id || '';
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(problemOf(e));
        this.loading.set(false);
      },
    });
  }

  compare() {
    if (this.base === this.target) return;
    this.comparing.set(true);
    this.compareError.set(null);
    this.api.compare(this.id, this.base, this.target).subscribe({
      next: (r) => {
        this.result.set(r);
        this.comparing.set(false);
      },
      error: (e) => {
        this.compareError.set(problemOf(e));
        this.comparing.set(false);
      },
    });
  }
}
