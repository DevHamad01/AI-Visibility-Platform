import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ApiService } from './api.service';
import { firstValueFrom } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('API boundaries', () => {
  let api: ApiService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    vi.unstubAllGlobals();
  });
  it('keeps one idempotency key on an explicit run request', () => {
    api.startRun('brand', 'stable-key').subscribe();
    const request = http.expectOne('/api/v1/brands/brand/runs');
    expect(request.request.headers.get('Idempotency-Key')).toBe('stable-key');
    request.flush({ id: 'run' });
  });
  it('loads all competitor pages before exposing the complete list', async () => {
    const result = firstValueFrom(api.competitors('brand'));
    http
      .expectOne((r) => r.url.endsWith('/competitors') && !r.params.has('cursor'))
      .flush({ items: [{ id: 'first' }], next_cursor: 'next' });
    http
      .expectOne((r) => r.params.get('cursor') === 'next')
      .flush({ items: [{ id: 'second' }], next_cursor: null });
    expect((await result).map((c) => c.id)).toEqual(['first', 'second']);
  });
  it('closes the event stream on terminal status and on unsubscribe', () => {
    class FakeEventSource {
      static last: FakeEventSource;
      onmessage: ((event: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      constructor() {
        FakeEventSource.last = this;
      }
    }
    vi.stubGlobal('EventSource', FakeEventSource);
    const received: string[] = [];
    api.events('run').subscribe((event) => received.push(event.status!));
    const stream = FakeEventSource.last;
    stream.onmessage!({ data: JSON.stringify({ status: 'partial' }) });
    expect(received).toEqual(['partial']);
    expect(stream.close).toHaveBeenCalledOnce();
    const sub = api.events('second').subscribe();
    const second = FakeEventSource.last;
    sub.unsubscribe();
    expect(second.close).toHaveBeenCalledOnce();
  });
  it('reports malformed stream data through the error channel', () => {
    class Fake {
      onmessage: ((e: { data: string }) => void) | null = null;
      onerror = null;
      close = vi.fn();
      constructor() {
        instance = this;
      }
    }
    let instance: Fake;
    vi.stubGlobal('EventSource', Fake);
    const error = vi.fn();
    api.events('run').subscribe({ error });
    instance!.onmessage!({ data: 'not-json' });
    expect(error).toHaveBeenCalledOnce();
    expect(instance!.close).toHaveBeenCalledOnce();
  });
});
