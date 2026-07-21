import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { Observable, throwError, BehaviorSubject } from 'rxjs';
import { map, catchError, tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { LoginPayload, LoginResponse } from '../helpers/model/authentication.model';

@Injectable({
  providedIn: 'root'
})
export class AuthenticationService {
  private readonly API_URL = environment.apiBaseUrl;
  private isAuthenticatedSubject = new BehaviorSubject<boolean>(this.hasToken());
  
  public isAuthenticated$ = this.isAuthenticatedSubject.asObservable();

  constructor(private http: HttpClient) {}

  login(credentials: LoginPayload): Observable<LoginResponse> {
    const loginUrl = `${this.API_URL}/users/login/`;
    const headers = new HttpHeaders({
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    });

    return this.http.post<LoginResponse>(loginUrl, credentials, { headers }).pipe(
     // In your authentication.service.ts login method, update the tap operator:
tap(response => {
  if (response.access) {
    localStorage.setItem('access_token', response.access);
    
    if (response.refresh) {
      localStorage.setItem('refresh_token', response.refresh);
    }
    
    // **IMPROVED**: Store actual username from response or credentials
    const user = {
      username: response.user.first_name || credentials.email, // Use actual username
      id: response.user.id || response.user.first_name || credentials.email, // Store proper ID
      email: response.user.email || `${response.user.first_name || credentials.email}@example.com`
    };
    
    localStorage.setItem('user', JSON.stringify(user));
    
    const storedToken = localStorage.getItem('access_token');
    const storedUser = localStorage.getItem('user');
    
    if (storedToken && storedUser) {
      this.isAuthenticatedSubject.next(true);
    } 
  } 
})
,
      map(response => {
      
        return response;
      }),
      catchError((error: HttpErrorResponse) => {
       
        
        let errorMessage = 'Login failed; please try again.';
        
        if (error.status === 400) {
          errorMessage = error.error?.message || error.error?.error || 'Invalid username or password.';
        } else if (error.status === 401) {
          errorMessage = 'Invalid credentials.';
        } else if (error.status === 500) {
          errorMessage = 'Server error. Please try again later.';
        } else if (error.status === 0) {
          errorMessage = 'Cannot connect to server. Please check your connection.';
        }
        
        return throwError(() => new Error(errorMessage));
      })
    );
  }

  private hasToken(): boolean {
    const token = localStorage.getItem('access_token');
    const hasToken = !!token;
    
    if (hasToken) {
     
    }
    return hasToken;
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  getUser(): any {
    try {
      const userStr = localStorage.getItem('user');
      return userStr ? JSON.parse(userStr) : null;
    } catch (error) {
      console.error('Error parsing user info:', error);
      return null;
    }
  }

  logout(): Observable<any> {
   
    
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    this.isAuthenticatedSubject.next(false);
    
    return this.http.post(`${this.API_URL}/api/logout/`, {}).pipe(
      catchError(error => {
        console.error('Logout error:', error);
        return throwError(() => error);
      })
    );
  }

  isLoggedIn(): boolean {
    return this.hasToken();
  }

  // **ENHANCED DEBUG METHOD**
  debugAuthState(): void {
    const token = localStorage.getItem('access_token');
    const user = localStorage.getItem('user');
    const refresh = localStorage.getItem('refresh_token');

    
    // **DECODE JWT TOKEN INFO** (if present)
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        
      } catch (e) {
        
      }
    }
    
    
  }

  // **HELPER METHOD**: Check if token is expired
  isTokenExpired(): boolean {
    const token = this.getToken();
    if (!token) return true;
    
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const exp = payload.exp * 1000; // Convert to milliseconds
      return Date.now() >= exp;
    } catch (error) {
      
      return true; // Assume expired if can't parse
    }
  }

  // **HELPER METHOD**: Force token refresh if needed
  checkTokenValidity(): boolean {
    const hasToken = this.hasToken();
    const isExpired = this.isTokenExpired();
    
    if (hasToken && !isExpired) {
      return true;
    }
    
    if (hasToken && isExpired) {
     
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      this.isAuthenticatedSubject.next(false);
    }
    
    return false;
  }
}
