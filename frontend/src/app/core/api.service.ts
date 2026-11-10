import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, expand, EMPTY, map, reduce } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  Brand,
  BrandInput,
  Comparison,
  Competitor,
  CompetitorInput,
  Opportunity,
  Overview,
  Page,
  Recommendation,
  RecommendationStatus,
  Run,
  RunEvent,
  RunSummary,
  VisibilityMatrix,
} from './models';
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  readonly base = environment.apiUrl;
  overview() {
    return this.http.get<Overview>(`${this.base}/overview`);
  }
  brand(id: string) {
    return this.http.get<Brand>(`${this.base}/brands/${id}`);
  }
  createBrand(body: BrandInput) {
    return this.http.post<Brand>(`${this.base}/brands`, body);
  }
  updateBrand(id: string, body: Partial<BrandInput>) {
    return this.http.patch<Brand>(`${this.base}/brands/${id}`, body);
  }
  competitors(id: string) {
    return this.allPages<Competitor>(`${this.base}/brands/${id}/competitors`);
  }
  addCompetitor(id: string, body: CompetitorInput) {
    return this.http.post<Competitor>(`${this.base}/brands/${id}/competitors`, body);
  }
  removeCompetitor(id: string, competitor: string) {
    return this.http.delete<void>(`${this.base}/brands/${id}/competitors/${competitor}`);
  }
  runs(id: string) {
    return this.http.get<Page<RunSummary>>(`${this.base}/brands/${id}/runs`, {
      params: { limit: 100 },
    });
  }
  startRun(id: string, key: string) {
    return this.http.post<RunSummary>(
      `${this.base}/brands/${id}/runs`,
      {},
      { headers: { 'Idempotency-Key': key } },
    );
  }
  run(id: string) {
    return this.http.get<Run>(`${this.base}/runs/${id}`);
  }
  visibility(id: string) {
    return this.http.get<VisibilityMatrix>(`${this.base}/runs/${id}/visibility`);
  }
  opportunities(id: string, filters: Record<string, string | number> = {}) {
    return this.http.get<Page<Opportunity>>(`${this.base}/runs/${id}/opportunities`, {
      params: { limit: 200, ...filters },
    });
  }
  recommendations(id: string) {
    return this.http.get<Page<Recommendation>>(`${this.base}/runs/${id}/recommendations`, {
      params: { limit: 100 },
    });
  }
  updateRecommendation(id: string, status: RecommendationStatus) {
    return this.http.patch<Recommendation>(`${this.base}/recommendations/${id}`, { status });
  }
  compare(id: string, base: string, target: string) {
    return this.http.get<Comparison>(`${this.base}/brands/${id}/compare`, {
      params: { base, target },
    });
  }
  exportUrl(id: string, format: 'csv' | 'json') {
    return `${this.base}/runs/${id}/export?format=${format}`;
  }
  events(id: string): Observable<RunEvent> {
    return new Observable((subscriber) => {
      const source = new EventSource(`${this.base}/runs/${id}/events`);
      source.onmessage = (event) => {
        try {
          const payload: RunEvent = JSON.parse(event.data);
          subscriber.next(payload);
          if (payload.status && !['queued', 'running'].includes(payload.status))
            subscriber.complete();
          if (payload.error || payload.warning)
            subscriber.error(new Error(payload.error || payload.warning));
        } catch (error) {
          subscriber.error(error);
        }
      };
      source.onerror = () =>
        subscriber.error(new Error('Live connection interrupted. Checking run status.'));
      return () => source.close();
    });
  }
  private allPages<T>(url: string): Observable<T[]> {
    const get = (cursor?: string) =>
      this.http.get<Page<T>>(url, {
        params: new HttpParams({ fromObject: { limit: 100, ...(cursor ? { cursor } : {}) } }),
      });
    return get().pipe(
      expand((page) => (page.next_cursor ? get(page.next_cursor) : EMPTY)),
      map((page) => page.items),
      reduce((all, items) => [...all, ...items], [] as T[]),
    );
  }
}
