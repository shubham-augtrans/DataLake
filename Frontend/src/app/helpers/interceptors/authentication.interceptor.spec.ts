import { TestBed } from '@angular/core/testing';
import { HttpInterceptorFn } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { authenticationInterceptor } from './authentication.interceptor';

describe('authenticationInterceptor', () => {
  const interceptor: HttpInterceptorFn = (req, next) =>
    TestBed.runInInjectionContext(() => authenticationInterceptor(req, next));

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([])]
    });
  });

  it('should be created', () => {
    expect(interceptor).toBeTruthy();
  });
});
