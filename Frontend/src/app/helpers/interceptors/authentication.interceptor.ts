import { HttpInterceptorFn } from '@angular/common/http';
import { Constant } from '../constants/constants';

export const authenticationInterceptor: HttpInterceptorFn = (req, next) => {
  const ACCESS_TOKEN = localStorage.getItem(Constant.ACCESS_TOKEN);

  if (ACCESS_TOKEN) {
    const AUTH_REQUEST = req.clone({
      setHeaders: {
        Authorization: `Bearer ${ACCESS_TOKEN}`
      }
    });
    return next(AUTH_REQUEST);
  }
  return next(req);
};