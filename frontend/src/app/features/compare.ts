import { Component, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { Comparison, Problem, RunSummary } from '../core/models';
import { problemOf } from '../core/errors';
import { Badge, Empty, ErrorState, Loading } from '../shared/ui';
@Component({
  imports: [RouterLink, FormsModule, DatePipe, DecimalPipe, Badge, Empty, ErrorState, Loading],
  template: ` <a class="back-link" [routerLink]="['/brands', id]">← Brand workspace</a>
    <div class="page-head">
      <div>
        <span class="eyebrow">Measure the change</span>
        <h1>Compare analyses</h1>
        <p>See which visibility gaps grew, shrank or appeared between two runs.</p>
      </div>
    </div>
    @if (error(); as p) {
      <app-error [problem]="p" (retry)="load()" />
    }
    @if (loading()) {
      <app-loading />
    } @else if (runs().length < 2) {
      <app-empty
        title="Two analyses tell a better story"
        text="Complete at least two analyses for this brand to compare their results."
      />
    } @else {
      <div class="card">
        <div class="filters">
          <div>
            <label for="base">Baseline analysis</label
            ><select id="base" [(ngModel)]="base" (ngModelChange)="result.set(null)">
              @for (run of runs(); track run.id) {
                <option [value]="run.id">
                  {{ run.created_at | date: 'MMM d, HH:mm' }} · {{ run.status }} ·
                  {{ run.id.slice(0, 8) }}
                </option>
              }
            </select>
          </div>
          <div>
            <label for="target">Target analysis</label
            ><select id="target" [(ngModel)]="target" (ngModelChange)="result.set(null)">
              @for (run of runs(); track run.id) {
                <option [value]="run.id">
                  {{ run.created_at | date: 'MMM d, HH:mm' }} · {{ run.status }} ·
                  {{ run.id.slice(0, 8) }}
                </option>
              }
            </select>
          </div>
          <button
            class="btn primary"
            (click)="compare()"
            [disabled]="base === target || comparing()"
          >
            {{ comparing() ? 'Comparing…' : 'Compare runs ⇄' }}
          </button>
        </div>
        <p class="field-help">
          A lower opportunity score means the remaining gap is smaller. Changes can also reflect
          demand, difficulty or competitor presence; they do not isolate visibility alone.
        </p>
      </div>
      @if (compareError(); as p) {
        <app-error [problem]="p" (retry)="compare()" />
      }
      @if (result(); as data) {
        @if (!data.deltas.length) {
          <app-empty
            title="No scored queries to compare"
            text="These runs contain no opportunity scores. Open each run’s trace to check whether data collection succeeded."
          />
        } @else {
          <div class="card flush table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Search query</th>
                  <th>Baseline gap</th>
                  <th>Target gap</th>
                  <th>Change</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                @for (d of data.deltas; track d.query_text) {
                  <tr>
                    <td>{{ d.query_text }}</td>
                    <td>{{ d.base_score === null ? '—' : (d.base_score | number: '1.1-1') }}</td>
                    <td>
                      {{ d.target_score === null ? '—' : (d.target_score | number: '1.1-1') }}
                    </td>
                    <td>{{ d.delta === null ? '—' : (d.delta | number: '1.1-1') }}</td>
                    <td><app-badge [status]="d.change" /></td>
                  </tr>
                }
              </tbody>
            </table>
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
  constructor() {
    this.load();
  }
  load() {
    this.error.set(null);
    this.loading.set(true);
    this.api.runs(this.id).subscribe({
      next: (p) => {
        this.runs.set(p.items);
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
