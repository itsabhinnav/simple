import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule, AbstractControl } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { TranslatePipe } from '../services/translate.pipe';

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterModule, TranslatePipe],
  template: `
    <div class="auth-container">
      <div class="auth-card">
        <div class="auth-header">
          <h1>Sakura</h1>
          <p>{{ 'login.signup_title' | translate }}</p>
        </div>

        <form [formGroup]="signupForm" (ngSubmit)="onSubmit()" class="auth-form">
          <div *ngIf="error()" class="error-message">
            {{ error() }}
          </div>

          <div class="form-group">
            <label for="username">{{ 'login.username' | translate }}</label>
            <input 
              type="text" 
              id="username"
              formControlName="username"
              class="form-input"
              placeholder="Choose a username"
              [class.error]="signupForm.get('username')?.invalid && signupForm.get('username')?.touched">
            <div *ngIf="signupForm.get('username')?.invalid && signupForm.get('username')?.touched" class="field-error">
              {{ 'login.username_min' | translate }}
            </div>
          </div>

          <div class="form-group">
            <label for="email">{{ 'login.email' | translate }}</label>
            <input 
              type="email" 
              id="email"
              formControlName="email"
              class="form-input"
              placeholder="Enter your email"
              [class.error]="signupForm.get('email')?.invalid && signupForm.get('email')?.touched">
            <div *ngIf="signupForm.get('email')?.invalid && signupForm.get('email')?.touched" class="field-error">
              <span *ngIf="signupForm.get('email')?.errors?.['required']">{{ 'login.email_required' | translate }}</span>
              <span *ngIf="signupForm.get('email')?.errors?.['email']">{{ 'login.email_invalid' | translate }}</span>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="first_name">{{ 'login.first_name_opt' | translate }}</label>
              <input 
                type="text" 
                id="first_name"
                formControlName="first_name"
                class="form-input"
                placeholder="First name">
            </div>

            <div class="form-group">
              <label for="last_name">{{ 'login.last_name_opt' | translate }}</label>
              <input 
                type="text" 
                id="last_name"
                formControlName="last_name"
                class="form-input"
                placeholder="Last name">
            </div>
          </div>

          <div class="form-group">
            <label for="password">{{ 'login.password' | translate }}</label>
            <input 
              type="password" 
              id="password"
              formControlName="password"
              class="form-input"
              placeholder="Create a password"
              [class.error]="signupForm.get('password')?.invalid && signupForm.get('password')?.touched">
            <div *ngIf="signupForm.get('password')?.invalid && signupForm.get('password')?.touched" class="field-error">
              {{ 'login.password_min' | translate }}
            </div>
          </div>

          <div class="form-group">
            <label for="confirmPassword">{{ 'login.confirm_password' | translate }}</label>
            <input 
              type="password" 
              id="confirmPassword"
              formControlName="confirmPassword"
              class="form-input"
              placeholder="Confirm your password"
              [class.error]="signupForm.get('confirmPassword')?.invalid && signupForm.get('confirmPassword')?.touched">
            <div *ngIf="signupForm.get('confirmPassword')?.invalid && signupForm.get('confirmPassword')?.touched" class="field-error">
              <span *ngIf="signupForm.get('confirmPassword')?.errors?.['required']">{{ 'login.confirm_password_required' | translate }}</span>
              <span *ngIf="signupForm.get('confirmPassword')?.errors?.['passwordsDoNotMatch']">{{ 'login.passwords_dont_match' | translate }}</span>
            </div>
          </div>

          <div class="form-group">
            <label for="secret_key">{{ 'login.secret_key' | translate }}</label>
            <input 
              type="text" 
              id="secret_key"
              formControlName="secret_key"
              class="form-input"
              placeholder="Enter a secret key to recover your password"
              [class.error]="signupForm.get('secret_key')?.invalid && signupForm.get('secret_key')?.touched">
            <div *ngIf="signupForm.get('secret_key')?.invalid && signupForm.get('secret_key')?.touched" class="field-error">
              {{ 'login.secret_key_min' | translate }}
            </div>
            <div class="field-hint">{{ 'login.secret_hint' | translate }}</div>
          </div>

          <button 
            type="submit" 
            class="btn-primary"
            [disabled]="signupForm.invalid || isLoading()">
            <span *ngIf="isLoading()" class="spinner-small"></span>
            {{ isLoading() ? ('login.creating_account' | translate) : ('login.signup_button' | translate) }}
          </button>
        </form>

        <div class="auth-footer">
          <p>{{ 'login.has_account' | translate }}
            <a routerLink="/login" class="link">{{ 'login.login_button' | translate }}</a>
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
      max-width: 480px;
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

    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
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

    .field-hint {
      color: #5f6368;
      font-size: 12px;
      margin-top: 2px;
      line-height: 1.4;
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

    @media (max-width: 768px) {
      .form-row {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class SignupComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  private formBuilder = inject(FormBuilder);

  signupForm: FormGroup;
  isLoading = signal(false);
  error = signal<string | null>(null);

  constructor() {
    this.signupForm = this.formBuilder.group({
      username: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(50)]],
      email: ['', [Validators.required, Validators.email]],
      first_name: [''],
      last_name: [''],
      password: ['', [Validators.required, Validators.minLength(12), Validators.maxLength(128)]],
      confirmPassword: ['', [Validators.required]],
      secret_key: ['', [Validators.required, Validators.minLength(12), Validators.maxLength(128)]],
      role: ['user']
    }, { validators: this.passwordMatchValidator });
  }

  passwordMatchValidator(control: AbstractControl): { [key: string]: any } | null {
    const password = control.get('password');
    const confirmPassword = control.get('confirmPassword');
    
    if (!password || !confirmPassword) {
      return null;
    }
    
    return password.value === confirmPassword.value ? null : { passwordsDoNotMatch: true };
  }

  onSubmit() {
    if (this.signupForm.invalid) {
      this.markFormGroupTouched();
      return;
    }

    this.isLoading.set(true);
    this.error.set(null);

    const signupData = {
      username: this.signupForm.value.username,
      email: this.signupForm.value.email,
      password: this.signupForm.value.password,
      first_name: this.signupForm.value.first_name || undefined,
      last_name: this.signupForm.value.last_name || undefined,
      secret_key: this.signupForm.value.secret_key,
      role: this.signupForm.value.role || 'user'
    };

    this.authService.signup(signupData).subscribe({
      next: () => {
        this.isLoading.set(false);
        // Redirect to dashboard
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading.set(false);
        const errorMessage = err.error?.message || err.error?.error || 'Signup failed';
        this.error.set(errorMessage);
      }
    });
  }

  private markFormGroupTouched() {
    Object.keys(this.signupForm.controls).forEach(key => {
      this.signupForm.get(key)?.markAsTouched();
    });
  }
}
