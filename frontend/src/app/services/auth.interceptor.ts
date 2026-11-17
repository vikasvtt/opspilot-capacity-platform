import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  if (request.url.includes('/auth/refresh')) return next(request);
  const token = auth.accessToken();
  const authorized = token ? request.clone({setHeaders: {Authorization: `Bearer ${token}`}}) : request;
  return next(authorized).pipe(catchError((error: unknown) => {
    if (!(error instanceof HttpErrorResponse) || error.status !== 401 || !auth.tokens()) return throwError(() => error);
    return from(auth.refresh()).pipe(
      switchMap(() => {
        const renewed = auth.accessToken();
        return next(request.clone({setHeaders: renewed ? {Authorization: `Bearer ${renewed}`} : {}}));
      }),
      catchError(refreshError => { auth.logout(); return throwError(() => refreshError); }),
    );
  }));
};
