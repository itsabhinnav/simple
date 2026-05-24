import { Injectable, signal, effect } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';
import { APP_SETTINGS, AUTH_DISABLED_USER } from '../app-settings';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface SignupRequest {
  username: string;
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  role?: string;
  secret_key: string;
  git_token?: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  data: {
    user: User;
    token: string;
  };
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly API_URL = 'http://localhost:5000/api/auth';
  /** Public, read-only flag: when false, the app runs without any login/signup flow. */
  readonly authEnabled = APP_SETTINGS.auth.enabled;
  private currentUser = signal<User | null>(null);
  private token = signal<string | null>(null);
  private isInitialized = signal(false);
  
  constructor(private http: HttpClient) {
    if (!this.authEnabled) {
      // Auth disabled (server-hosted single-tenant deployment): synthesize a
      // workspace user so every guard/service downstream sees an authenticated
      // admin and never makes auth API calls.
      this.currentUser.set({ ...AUTH_DISABLED_USER });
      this.token.set(null);
      this.isInitialized.set(true);
      return;
    }
    // Load token synchronously from storage
    this.loadTokenFromStorage();
    // Defer the "ready" flip to the next macrotask so components don't render
    // before signals settle, preventing a login flash on refresh.
    setTimeout(() => {
      this.isInitialized.set(true);
    }, 0);
  }
  
  getIsInitialized(): boolean {
    return this.isInitialized();
  }
  
  /**
   * Sign up a new user
   */
  signup(data: SignupRequest): Observable<AuthResponse> {
    if (!this.authEnabled) {
      return of(this.makeDisabledAuthResponse('Signup is disabled in this deployment'));
    }
    return this.http.post<AuthResponse>(`${this.API_URL}/signup`, data).pipe(
      tap((response) => {
        if (response.success && response.data) {
          this.setAuthData(response.data.user, response.data.token);
        }
      }),
      catchError((error) => {
        console.error('Signup error:', error);
        return throwError(() => error);
      })
    );
  }
  
  /**
   * Login user
   */
  login(credentials: LoginRequest): Observable<AuthResponse> {
    if (!this.authEnabled) {
      return of(this.makeDisabledAuthResponse('Login is disabled in this deployment'));
    }
    return this.http.post<AuthResponse>(`${this.API_URL}/login`, credentials).pipe(
      tap((response) => {
        if (response.success && response.data) {
          this.setAuthData(response.data.user, response.data.token);
        }
      }),
      catchError((error) => {
        console.error('Login error:', error);
        return throwError(() => error);
      })
    );
  }
  
  /**
   * Logout user
   */
  logout(): void {
    if (!this.authEnabled) {
      // Logout is meaningless when auth is disabled; keep the workspace user.
      return;
    }
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
    this.token.set(null);
    this.currentUser.set(null);
  }
  
  /**
   * Get current user
   */
  getCurrentUser(): User | null {
    return this.currentUser();
  }
  
  /**
   * Get auth token
   */
  getToken(): string | null {
    return this.token();
  }
  
  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    if (!this.authEnabled) {
      return true;
    }
    return this.token() !== null;
  }
  
  /**
   * Verify token with backend
   */
  verifyToken(): Observable<{ success: boolean; data: User }> {
    if (!this.authEnabled) {
      const user = { ...AUTH_DISABLED_USER };
      this.currentUser.set(user);
      return of({ success: true, data: user });
    }
    return this.http.get<{ success: boolean; data: User }>(`${this.API_URL}/verify`, {
      headers: this.getAuthHeaders()
    }).pipe(
      tap((response) => {
        if (response.success && response.data) {
          this.currentUser.set(response.data);
        }
      }),
      catchError((error) => {
        console.error('Token verification error:', error);
        this.logout();
        return throwError(() => error);
      })
    );
  }
  
  /**
   * Get HTTP headers with authorization
   */
  getAuthHeaders(): { [key: string]: string } {
    const token = this.getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }
  
  /**
   * Set authentication data
   */
  private setAuthData(user: User, token: string): void {
    this.currentUser.set(user);
    this.token.set(token);
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', token);
      localStorage.setItem('user', JSON.stringify(user));
    }
  }
  
  /**
   * Verify secret key for password reset
   */
  verifySecretKey(username: string, secret_key: string): Observable<{ success: boolean }> {
    if (!this.authEnabled) {
      return of({ success: false });
    }
    return this.http.post<{ success: boolean }>(`${this.API_URL}/verify-secret`, {
      username,
      secret_key
    });
  }

  /**
   * Reset password
   */
  resetPassword(username: string, new_password: string): Observable<{ success: boolean; message: string }> {
    if (!this.authEnabled) {
      return of({ success: false, message: 'Password reset is disabled in this deployment' });
    }
    return this.http.post<{ success: boolean; message: string }>(`${this.API_URL}/reset-password`, {
      username,
      new_password
    });
  }

  /**
   * Load token from storage on initialization
   */
  private loadTokenFromStorage(): void {
    if (typeof window === 'undefined') {
      return; // Not in browser, skip
    }
    
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    
    if (storedToken && storedUser) {
      this.token.set(storedToken);
      try {
        this.currentUser.set(JSON.parse(storedUser));
      } catch (e) {
        console.error('Failed to parse stored user:', e);
        this.logout();
      }
    }
  }

  /**
   * Build a synthetic AuthResponse used when auth is disabled so callers that
   * expect the standard shape (subscribe `next`, then navigate) still work
   * without touching the network.
   */
  private makeDisabledAuthResponse(message: string): AuthResponse {
    const user = { ...AUTH_DISABLED_USER };
    return {
      success: true,
      message,
      data: { user, token: '' }
    };
  }
}
