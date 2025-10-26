import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterModule],
  template: `
    <div class="auth-container">
      <div class="auth-card">
        <div class="auth-header">
          <h1>Sakura</h1>
          <p>Login to your account</p>
        </div>

        <form [formGroup]="loginForm" (ngSubmit)="onSubmit()" class="auth-form">
          <div *ngIf="error()" class="error-message">
            {{ error() }}
          </div>

          <div class="form-group">
            <label for="username">Username</label>
            <input 
              type="text" 
              id="username"
              formControlName="username"
              class="form-input"
              placeholder="Enter your username"
              [class.error]="loginForm.get('username')?.invalid && loginForm.get('username')?.touched">
            <div *ngIf="loginForm.get('username')?.invalid && loginForm.get('username')?.touched" class="field-error">
              Username is required
            </div>
          </div>

          <div class="form-group">
            <label for="password">Password</label>
            <input 
              type="password" 
              id="password"
              formControlName="password"
              class="form-input"
              placeholder="Enter your password"
              [class.error]="loginForm.get('password')?.invalid && loginForm.get('password')?.touched">
            <div *ngIf="loginForm.get('password')?.invalid && loginForm.get('password')?.touched" class="field-error">
              Password is required (min 6 characters)
            </div>
          </div>

          <button 
            type="submit" 
            class="btn-primary"
            [disabled]="loginForm.invalid || isLoading()">
            <span *ngIf="isLoading()" class="spinner-small"></span>
            {{ isLoading() ? 'Logging in...' : 'Login' }}
          </button>
        </form>

        <div class="auth-footer">
          <p>Don't have an account? 
            <a routerLink="/signup" class="link">Sign up</a>
          </p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-container {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: var(--spacing-lg);
      background-color: var(--color-gray-200);
    }

    .auth-card {
      width: 100%;
      max-width: 420px;
      background: var(--color-gray-100);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius-lg);
      padding: var(--spacing-xl);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }

    .auth-header {
      text-align: center;
      margin-bottom: var(--spacing-lg);
    }

    .auth-header h1 {
      font-size: 2rem;
      font-weight: 600;
      color: var(--color-primary);
      margin-bottom: var(--spacing-sm);
    }

    .auth-header p {
      color: var(--color-primary-lighter);
      font-size: 14px;
    }

    .auth-form {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-md);
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-xs);
    }

    .form-group label {
      font-size: 14px;
      font-weight: 500;
      color: var(--color-primary);
    }

    .form-input {
      padding: var(--spacing-sm) var(--spacing-md);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius-sm);
      font-size: 16px;
      background-color: var(--color-gray-100);
      transition: border-color 0.2s;
    }

    .form-input:focus {
      outline: none;
      border-color: var(--color-accent);
      box-shadow: 0 0 0 2px var(--color-accent-light);
    }

    .form-input.error {
      border-color: #c62828;
    }

    .field-error {
      color: #c62828;
      font-size: 12px;
      margin-top: 2px;
    }

    .error-message {
      padding: var(--spacing-sm) var(--spacing-md);
      background-color: #ffebee;
      color: #c62828;
      border: 1px solid #ffcdd2;
      border-radius: var(--border-radius-sm);
      font-size: 14px;
      margin-bottom: var(--spacing-md);
    }

    .btn-primary {
      padding: var(--spacing-sm) var(--spacing-lg);
      background-color: var(--color-primary);
      color: var(--color-gray-100);
      border: 1px solid var(--color-primary);
      border-radius: var(--border-radius-sm);
      font-size: 16px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-xs);
      margin-top: var(--spacing-md);
    }

    .btn-primary:hover:not(:disabled) {
      background-color: var(--color-primary-light);
      border-color: var(--color-primary-light);
    }

    .btn-primary:disabled {
      background-color: var(--color-gray-400);
      border-color: var(--color-gray-400);
      cursor: not-allowed;
      opacity: 0.6;
    }

    .spinner-small {
      width: 16px;
      height: 16px;
      border: 2px solid transparent;
      border-top: 2px solid currentColor;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .auth-footer {
      text-align: center;
      margin-top: var(--spacing-lg);
      padding-top: var(--spacing-lg);
      border-top: 1px solid var(--color-gray-300);
    }

    .auth-footer p {
      color: var(--color-primary-lighter);
      font-size: 14px;
    }

    .link {
      color: var(--color-accent);
      text-decoration: none;
      font-weight: 500;
    }

    .link:hover {
      text-decoration: underline;
    }
  `]
})
export class LoginComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  private formBuilder = inject(FormBuilder);

  loginForm: FormGroup;
  isLoading = signal(false);
  error = signal<string | null>(null);

  constructor() {
    this.loginForm = this.formBuilder.group({
      username: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(50)]],
      password: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(100)]]
    });
  }

  onSubmit() {
    if (this.loginForm.invalid) {
      this.markFormGroupTouched();
      return;
    }

    this.isLoading.set(true);
    this.error.set(null);

    const credentials = {
      username: this.loginForm.value.username,
      password: this.loginForm.value.password
    };

    this.authService.login(credentials).subscribe({
      next: () => {
        this.isLoading.set(false);
        // Redirect to dashboard
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading.set(false);
        const errorMessage = err.error?.message || err.error?.error || 'Login failed';
        this.error.set(errorMessage);
      }
    });
  }

  private markFormGroupTouched() {
    Object.keys(this.loginForm.controls).forEach(key => {
      this.loginForm.get(key)?.markAsTouched();
    });
  }
}

