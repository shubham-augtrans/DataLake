import { inject } from '@angular/core';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { Constant } from '../constants/constants';

export const authenticationInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const ACCESS_TOKEN = localStorage.getItem(Constant.ACCESS_TOKEN);

  const authRequest = ACCESS_TOKEN
    ? req.clone({ setHeaders: { Authorization: `Bearer ${ACCESS_TOKEN}` } })
    : req;

  return next(authRequest).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401) {
        localStorage.removeItem(Constant.ACCESS_TOKEN);
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        router.navigate(['/login']);
      }
      return throwError(() => error);
    })
  );
};