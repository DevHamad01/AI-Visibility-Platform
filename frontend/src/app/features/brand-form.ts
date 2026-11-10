import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators,
  AbstractControl,
  ValidationErrors,
} from '@angular/forms';
import { concatMap, forkJoin, of } from 'rxjs';
import { ApiService } from '../core/api.service';
import { Competitor, Problem } from '../core/models';
import { problemOf } from '../core/errors';
import { ErrorState, Loading } from '../shared/ui';
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
@Component({
  imports: [RouterLink, ReactiveFormsModule, ErrorState, Loading],
  template: `
    <a class="back-link" [routerLink]="id ? ['/brands', id] : ['/']">← Back to workspace</a>
    <div class="page-head">
      <div>
        <span class="eyebrow">Build your competitive picture</span>
        <h1>{{ id ? 'Brand settings' : 'Add a brand' }}</h1>
        <p>
          Tell us who you are and who you compete with. We’ll find where your next visibility
          opportunity lives.
        </p>
      </div>
    </div>
    @if (loading()) {
      <app-loading />
    } @else {
      <form [formGroup]="form" (ngSubmit)="save()" class="form-section">
        @if (error(); as p) {
          <app-error [problem]="p" (retry)="save()" />
        }
        <section class="card">
          <div class="section-head" style="margin-top:0">
            <div>
              <h2>01 &nbsp; Brand profile</h2>
              <p>The starting point for every analysis.</p>
            </div>
          </div>
          <div class="form-grid">
            <div>
              <label for="name">Brand name *</label
              ><input
                id="name"
                formControlName="name"
                placeholder="Your brand name"
                maxlength="200"
              />
              @if (invalid('name')) {
                <p class="field-error">Enter a brand name.</p>
              }
            </div>
            <div>
              <label for="domain">Website domain *</label
              ><input
                id="domain"
                formControlName="domain"
                placeholder="example.com"
                maxlength="255"
              />
              @if (invalid('domain')) {
                <p class="field-error">Enter a valid domain, such as example.com.</p>
              }
            </div>
            <div class="full">
              <label for="description">What does your brand do?</label
              ><textarea
                id="description"
                formControlName="description"
                rows="3"
                maxlength="5000"
                placeholder="Describe your product, audience and key use cases."
              ></textarea>
              <p class="field-help">This helps the query planner choose relevant searches.</p>
            </div>
            <div>
              <label for="industry">Industry</label
              ><input
                id="industry"
                formControlName="industry"
                placeholder="e.g. Project management software"
                maxlength="200"
              />
            </div>
            <div>
              <label for="language">Language code</label
              ><input
                id="language"
                formControlName="language_code"
                placeholder="en"
                maxlength="10"
              />
            </div>
            <div>
              <label for="location">Location code</label
              ><input
                id="location"
                type="number"
                formControlName="location_code"
                min="0"
                placeholder="Provider default"
              />
              <p class="field-help">
                Optional DataForSEO location code, e.g. 2840 for United States.
              </p>
            </div>
          </div>
        </section>
        <section class="card">
          <div class="section-head" style="margin-top:0">
            <div>
              <h2>02 &nbsp; Competitors</h2>
              <p>Track the brands your audience considers alongside yours.</p>
            </div>
            <button
              type="button"
              class="btn small"
              (click)="addCompetitor()"
              [disabled]="competitors.length + existing().length >= 9"
            >
              ＋ Add competitor
            </button>
          </div>
          @if (existing().length) {
            <p class="field-help">Already tracked</p>
            <div class="chip-list">
              @for (c of existing(); track c.id) {
                <span class="chip">{{ c.name }} · {{ c.domain }}</span>
              }
            </div>
          }
          <div formArrayName="competitors">
            @for (group of competitors.controls; track group; let i = $index) {
              <div class="competitor-row" [formGroupName]="i">
                <div>
                  <label [for]="'cname' + i">Competitor name</label
                  ><input
                    [id]="'cname' + i"
                    formControlName="name"
                    placeholder="Competitor name"
                    maxlength="200"
                  />
                </div>
                <div>
                  <label [for]="'cdomain' + i">Domain</label
                  ><input
                    [id]="'cdomain' + i"
                    formControlName="domain"
                    placeholder="competitor.com"
                    maxlength="255"
                  />
                </div>
                <button
                  class="btn small"
                  type="button"
                  style="margin-top:26px"
                  (click)="competitors.removeAt(i)"
                  [attr.aria-label]="'Remove competitor ' + (i + 1)"
                >
                  Remove
                </button>
              </div>
              @if (group.invalid && group.touched) {
                <p class="field-error">Each competitor needs a name and valid domain.</p>
              }
            }
          </div>
          @if (!competitors.length && !existing().length) {
            <p class="muted small-text">No competitors yet. You can add them now or later.</p>
          }
        </section>
        <div class="form-actions">
          <a class="btn" [routerLink]="id ? ['/brands', id] : ['/']">Cancel</a
          ><button class="btn primary" type="submit" [disabled]="saving()">
            {{ saving() ? 'Saving…' : id ? 'Save changes' : 'Create brand →' }}
          </button>
        </div>
      </form>
    }
  `,
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
          // Add sequentially. Successful rows are removed so a retry cannot duplicate them.
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
