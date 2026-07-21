import { Component, inject, OnDestroy } from '@angular/core';
import { DividerModule } from 'primeng/divider';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import {
  FormBuilder,
  FormsModule,
  Validators,
  ReactiveFormsModule,
  FormGroup
} from '@angular/forms';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { CommonModule } from '@angular/common';
import { PasswordModule } from 'primeng/password';

import { AuthenticationService } from '../../services/authentication.service';
import {
  LoginPayload,
  LoginResponse
} from '../../helpers/model/authentication.model';

import { takeUntil, finalize } from 'rxjs/operators';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    DividerModule,
    CommonModule,
    ReactiveFormsModule,
    ButtonModule,
    InputTextModule,
    FormsModule,
    PasswordModule
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent implements OnDestroy {

  fb = inject(FormBuilder);

  private destroyer$ = new Subject<void>();

  isLoading = false;
  errorMessage = '';

  userForm: FormGroup = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(2)]]
  });

  constructor(
    private router: Router,
    private authService: AuthenticationService
  ) {}

  onLogin(): void {

    if (this.userForm.invalid) {
      this.userForm.markAllAsTouched();
      return;
    }

    this.errorMessage = '';
    this.isLoading = true;

    const payload: LoginPayload = {
      email: this.userForm.value.email,
      password: this.userForm.value.password
    };

    this.authService.login(payload)
      .pipe(
        takeUntil(this.destroyer$),
        finalize(() => this.isLoading = false)
      )
      .subscribe({

        next: (data: LoginResponse) => {

          if (data.access) {

            localStorage.setItem('access_token', data.access);

            if (data.refresh) {
              localStorage.setItem('refresh_token', data.refresh);
            }

            if (data.user) {
              localStorage.setItem('user', JSON.stringify(data.user));
            }

           this.router.navigate(['/dashboard']);

          } else {

            this.errorMessage = 'No access token received.';
          }
        },

        error: (err) => {
          this.errorMessage =
            err?.error?.message ||
            err?.error?.detail ||
            'Invalid email or password.';
        }
      });
  }

  ngOnDestroy(): void {
    this.destroyer$.next();
    this.destroyer$.complete();
  }
}