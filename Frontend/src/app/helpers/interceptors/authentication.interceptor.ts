import { inject } from '@angular/core';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, catchError, filter, switchMap, take, throwError } from 'rxjs';
import { Constant } from '../constants/constants';
import { AuthenticationService } from '../../services/authentication.service';

// Module-level (not per-request) so concurrent requests that all 401 at
// once share a single refresh call instead of each firing their own -
// the second+ request just waits for the first's result.
let isRefreshing = false;
const refreshedToken$ = new BehaviorSubject<string | null>(null);

export const authenticationInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const auth = inject(AuthenticationService);
  const ACCESS_TOKEN = localStorage.getItem(Constant.ACCESS_TOKEN);

  const authRequest = ACCESS_TOKEN
    ? req.clone({ setHeaders: { Authorization: `Bearer ${ACCESS_TOKEN}` } })
    : req;

  const logout = () => {
    localStorage.removeItem(Constant.ACCESS_TOKEN);
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    router.navigate(['/login']);
  };

  return next(authRequest).pipe(
    catchError((error: HttpErrorResponse) => {
      // Never try to refresh using a 401 from the refresh call itself, or
      // from the login endpoint - those mean the session is genuinely gone.
      const isAuthEndpoint = req.url.includes('/token/refresh/') || req.url.includes('/login/');

      if (error.status !== 401 || isAuthEndpoint) {
        return throwError(() => error);
      }

      if (!isRefreshing) {
        isRefreshing = true;
        refreshedToken$.next(null);

        return auth.refreshAccessToken().pipe(
          switchMap(newToken => {
            isRefreshing = false;
            refreshedToken$.next(newToken);
            return next(req.clone({ setHeaders: { Authorization: `Bearer ${newToken}` } }));
          }),
          catchError(refreshError => {
            isRefreshing = false;
            logout();
            return throwError(() => refreshError);
          })
        );
      }

      // A refresh is already in flight (triggered by another request that
      // 401'd around the same time) - wait for it to finish, then retry
      // this request with the token it produced.
      return refreshedToken$.pipe(
        filter(token => token !== null),
        take(1),
        switchMap(token => next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })))
      );
    })
  );
};
