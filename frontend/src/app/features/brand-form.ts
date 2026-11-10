import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { concatMap, forkJoin, of } from 'rxjs';
import { ApiService } from '../core/api.service';
import { problemOf } from '../core/errors';
import { Competitor, Problem } from '../core/models';
import { Icon } from '../shared/icon';
import { ErrorState, PageHeader, Skeleton } from '../shared/ui';

/** Mirrors the backend's domain rule so the field fails before a round-trip. */
export function domainValidator(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value || '')
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .split('/')[0];
  return /^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$/.test(value)
    ? null
    : { domain: true };
}

const MAX_COMPETITORS = 9;

@Component({
  imports: [RouterLink, ReactiveFormsModule, Icon, ErrorState, PageHeader, Skeleton],
  template: `<a
      [routerLink]="id ? ['/brands', id] : ['/']"
      class="mb-5 inline-flex items-center gap-1.5 text-label-sm font-medium text-ink-600 transition-colors duration-150 hover:text-ink-950"
    >
      <app-icon name="arrow-left" [size]="14" />
      {{ id ? 'Back to workspace' : 'Back to overview' }}
    </a>

    <app-page-header
      [eyebrow]="id ? 'Brand settings' : 'New brand'"
      [title]="id ? 'Edit brand' : 'Add a brand'"
      subtitle="Who you are and who you compete with. The query planner uses this to pick which searches to measure."
    />

    @if (loading()) {
      <app-skeleton variant="card" />
    } @else {
      <form [formGroup]="form" (ngSubmit)="save()" class="max-w-3xl space-y-4">
        @if (error(); as problem) {
          <app-error [problem]="problem" (retry)="save()" />
        }

        <!-- 01 · Brand profile -->
        <section class="card overflow-hidden">
          <div class="flex items-center gap-3 border-b-hairline border-stroke-200 px-4 py-3">
            <span
              class="tnum grid h-6 w-6 place-items-center rounded-6 bg-surface-100 text-label-xs font-semibold text-ink-600"
              >01</span
            >
            <div>
              <h2 class="panel-title">Brand profile</h2>
              <p class="mt-0.5 text-label-xs text-ink-400">
                The starting point for every analysis.
              </p>
            </div>
          </div>

          <div class="grid gap-4 p-4 sm:grid-cols-2">
            <div>
              <label class="field-label" for="name"
                >Brand name <span class="text-danger-700">*</span></label
              >
              <input
                id="name"
                formControlName="name"
                maxlength="200"
                placeholder="Acme Corp"
                class="input"
                [class.input-invalid]="invalid('name')"
                [attr.aria-invalid]="invalid('name')"
              />
              @if (invalid('name')) {
                <p class="field-error">
                  <app-icon name="alert-circle" [size]="12" /> Enter a brand name.
                </p>
              }
            </div>

            <div>
              <label class="field-label" for="domain"
                >Website domain <span class="text-danger-700">*</span></label
              >
              <input
                id="domain"
                formControlName="domain"
                maxlength="255"
                placeholder="acme.com"
                class="input"
                [class.input-invalid]="invalid('domain')"
                [attr.aria-invalid]="invalid('domain')"
              />
              @if (invalid('domain')) {
                <p class="field-error">
                  <app-icon name="alert-circle" [size]="12" /> Use a bare domain, like acme.com.
                </p>
              } @else {
                <p class="field-hint">No https:// and no path — just the domain.</p>
              }
            </div>

            <div class="sm:col-span-2">
              <label class="field-label" for="description">What does this brand do?</label>
              <textarea
                id="description"
                formControlName="description"
                rows="3"
                maxlength="5000"
                placeholder="Describe the product, who buys it, and the problems it solves."
                class="input resize-y"
              ></textarea>
              <p class="field-hint">
                Used by the planner to choose realistic buyer-intent searches — the more specific,
                the better the queries.
              </p>
            </div>

            <div>
              <label class="field-label" for="industry">Industry</label>
              <input
                id="industry"
                formControlName="industry"
                maxlength="200"
                placeholder="Project management software"
                class="input"
              />
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="field-label" for="language">Language</label>
                <input
                  id="language"
                  formControlName="language_code"
                  maxlength="10"
                  placeholder="en"
                  class="input"
                />
              </div>
              <div>
                <label class="field-label" for="location">Location</label>
                <input
                  id="location"
                  type="number"
                  formControlName="location_code"
                  min="0"
                  placeholder="2840"
                  class="input tnum"
                />
              </div>
            </div>
            <p class="field-hint sm:col-span-2 sm:-mt-2">
              Location is a DataForSEO code — 2840 is the United States. Leave blank for the
              provider default.
            </p>
          </div>
        </section>

        <!-- 02 · Competitors -->
        <section class="card overflow-hidden">
          <div
            class="flex flex-wrap items-center justify-between gap-3 border-b-hairline border-stroke-200 px-4 py-3"
          >
            <div class="flex items-center gap-3">
              <span
                class="tnum grid h-6 w-6 place-items-center rounded-6 bg-surface-100 text-label-xs font-semibold text-ink-600"
                >02</span
              >
              <div>
                <h2 class="panel-title">Competitors</h2>
                <p class="mt-0.5 text-label-xs text-ink-400">
                  Who your buyers compare you against. Drives the “contested” part of each score.
                </p>
              </div>
            </div>
            <button
              type="button"
              class="btn-secondary btn-sm"
              (click)="addCompetitor()"
              [disabled]="total() >= MAX_COMPETITORS"
            >
              <app-icon name="plus" [size]="12" /> Add
            </button>
          </div>

          <div class="space-y-4 p-4">
            @if (existing().length) {
              <div>
                <p class="eyebrow mb-2">Already tracked</p>
                <ul class="flex flex-wrap gap-1.5">
                  @for (c of existing(); track c.id) {
                    <li
                      class="inline-flex items-center gap-1.5 rounded-6 border-hairline border-stroke-200 bg-surface-50 px-2 py-1 text-label-xs text-ink-700"
                    >
                      <app-icon name="building" [size]="12" />
                      <span class="font-medium text-ink-950">{{ c.name }}</span>
                      <span class="text-ink-400">{{ c.domain }}</span>
                    </li>
                  }
                </ul>
              </div>
            }

            <div formArrayName="competitors" class="space-y-3">
              @for (group of competitors.controls; track group; let i = $index) {
                <div
                  [formGroupName]="i"
                  class="rounded-8 border-hairline border-stroke-200 bg-surface-50 p-3"
                >
                  <div class="flex items-end gap-3">
                    <div class="min-w-0 flex-1">
                      <label class="field-label" [for]="'cname' + i">Name</label>
                      <input
                        [id]="'cname' + i"
                        formControlName="name"
                        maxlength="200"
                        placeholder="Monday.com"
                        class="input"
                      />
                    </div>
                    <div class="min-w-0 flex-1">
                      <label class="field-label" [for]="'cdomain' + i">Domain</label>
                      <input
                        [id]="'cdomain' + i"
                        formControlName="domain"
                        maxlength="255"
                        placeholder="monday.com"
                        class="input"
                      />
                    </div>
                    <button
                      type="button"
                      class="btn-ghost btn-icon mb-0.5 text-ink-400 hover:text-danger-700"
                      (click)="competitors.removeAt(i)"
                      [attr.aria-label]="'Remove competitor ' + (i + 1)"
                    >
                      <app-icon name="trash" [size]="14" />
                    </button>
                  </div>
                  @if (group.invalid && group.touched) {
                    <p class="field-error">
                      <app-icon name="alert-circle" [size]="12" /> Each competitor needs a name and
                      a valid domain.
                    </p>
                  }
                </div>
              }
            </div>

            @if (!competitors.length && !existing().length) {
              <p class="flex items-center gap-1.5 text-label-xs text-ink-400">
                <app-icon name="info" [size]="12" /> No competitors yet — you can add them now or
                later from the workspace.
              </p>
            }
          </div>
        </section>

        <div class="flex items-center justify-end gap-2 pb-2">
          <a class="btn-secondary" [routerLink]="id ? ['/brands', id] : ['/']">Cancel</a>
          <button class="btn-primary" type="submit" [disabled]="saving()">
            @if (saving()) {
              <app-icon name="spinner" [size]="14" /> Saving…
            } @else {
              {{ id ? 'Save changes' : 'Create brand' }}
              <app-icon name="arrow-right" [size]="14" />
            }
          </button>
        </div>
      </form>
    }`,
})
export class BrandFormPage {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id');
  readonly saving = signal(false);
  readonly loading = signal(false);
  readonly error = signal<Problem | null>(null);
  readonly existing = signal<Competitor[]>([]);
  protected readonly MAX_COMPETITORS = MAX_COMPETITORS;

  private createdId: string | null = null;

  readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(200), Validators.pattern(/\S/)]],
    domain: ['', [Validators.required, domainValidator]],
    description: [''],
    industry: [''],
    language_code: ['en', [Validators.minLength(2), Validators.maxLength(10)]],
    location_code: [null as number | null, Validators.min(0)],
    competitors: this.fb.array<ReturnType<BrandFormPage['competitorGroup']>>([]),
  });

  get competitors() {
    return this.form.controls.competitors;
  }

  total() {
    return this.competitors.length + this.existing().length;
  }

  private competitorGroup() {
    return this.fb.group({
      name: ['', [Validators.required, Validators.pattern(/\S/)]],
      domain: ['', [Validators.required, domainValidator]],
    });
  }

  constructor() {
    if (this.id) {
      this.loading.set(true);
      forkJoin({
        brand: this.api.brand(this.id),
        competitors: this.api.competitors(this.id),
      }).subscribe({
        next: (data) => {
          this.form.patchValue({
            ...data.brand,
            description: data.brand.description || '',
            industry: data.brand.industry || '',
            language_code: data.brand.language_code || 'en',
            location_code: data.brand.location_code ?? null,
          });
          this.existing.set(data.competitors);
          this.loading.set(false);
        },
        error: (e) => {
          this.error.set(problemOf(e));
          this.loading.set(false);
        },
      });
    } else {
      this.addCompetitor();
      this.addCompetitor();
    }
  }

  addCompetitor() {
    this.competitors.push(this.competitorGroup());
  }

  invalid(name: 'name' | 'domain') {
    return this.form.controls[name].invalid && this.form.controls[name].touched;
  }

  save() {
    if (this.saving()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;

    this.saving.set(true);
    this.error.set(null);
    const raw = this.form.getRawValue();
    const body = {
      name: raw.name!.trim(),
      domain: raw.domain!.trim(),
      description: raw.description || null,
      industry: raw.industry || null,
      language_code: raw.language_code || null,
      location_code: raw.location_code,
    };

    const id = this.id || this.createdId;
    const saveBrand = id ? this.api.updateBrand(id, body) : this.api.createBrand(body);

    saveBrand
      .pipe(
        concatMap((brand) => {
          this.createdId = brand.id;
          // Added sequentially; each success is removed from the form so a
          // retry after a mid-list failure cannot duplicate earlier rows.
          const pending = [...this.competitors.controls];
          let chain = of(brand.id);
          for (const group of pending)
            chain = chain.pipe(
              concatMap((brandId) =>
                this.api
                  .addCompetitor(brandId, {
                    name: group.value.name!.trim(),
                    domain: group.value.domain!.trim(),
                  })
                  .pipe(
                    concatMap((c) => {
                      this.existing.update((items) => [...items, c]);
                      this.competitors.removeAt(this.competitors.controls.indexOf(group));
                      return of(brandId);
                    }),
                  ),
              ),
            );
          return chain;
        }),
      )
      .subscribe({
        next: (brandId) => {
          this.saving.set(false);
          void this.router.navigate(['/brands', brandId]);
        },
        error: (e) => {
          this.error.set(problemOf(e));
          this.saving.set(false);
        },
      });
  }
}
