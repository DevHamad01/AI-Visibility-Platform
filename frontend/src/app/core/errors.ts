import { ErrorHandler, Injectable, inject } from '@angular/core';
import {
  HttpBackend,
  HttpClient,
  HttpErrorResponse,
  HttpInterceptorFn,
} from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { Problem } from './models';
@Injectable({ providedIn: 'root' })
export class ErrorReporter {
  private readonly http = new HttpClient(inject(HttpBackend));
  report(message: string, requestId?: string) {
    this.http
      .post('/api/v1/client-errors', {
        message: message.slice(0, 2000),
        request_id: requestId,
        route: location.pathname.slice(0, 300),
      })
      .subscribe({ error: () => undefined });
  }
}
@Injectable()
export class AppErrorHandler implements ErrorHandler {
  private readonly reporter = inject(ErrorReporter);
  handleError(error: unknown) {
    console.error(error);
    this.reporter.report(error instanceof Error ? error.message : 'Unexpected application error');
  }
}
export const requestInterceptor: HttpInterceptorFn = (request, next) => {
  const reporter = inject(ErrorReporter);
  if (!request.url.startsWith('/api/')) return next(request);
  const id = crypto.randomUUID();
  return next(request.clone({ setHeaders: { 'X-Request-ID': id } })).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 0 || error.status >= 500)
        reporter.report(`HTTP ${error.status}: ${request.method} ${request.url.split('?')[0]}`, id);
      return throwError(() => error);
    }),
  );
};
export function problemOf(error: unknown): Problem {
  if (error instanceof HttpErrorResponse) {
    const body = typeof error.error === 'object' && error.error !== null ? error.error : {};
    return {
      ...body,
      title: body.title || 'Could not complete this request',
      detail:
        body.detail ||
        (error.status === 0
          ? 'The service is unreachable. Check your connection and try again.'
          : `Request failed (${error.status}). Please try again.`),
      trace_id: body.trace_id || error.headers.get('X-Request-ID'),
    };
  }
  return {
    title: 'Something needs attention',
    detail: error instanceof Error ? error.message : 'Please try again.',
  };
}
