import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [CommonModule, RouterModule, ReactiveFormsModule],
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.scss'
})
export class ForgotPasswordComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  private formBuilder = inject(FormBuilder);

  step = signal<1 | 2 | 3>(1); // 1: verify identity, 2: reset password, 3: success
  error = signal<string | null>(null);
  isProcessing = signal(false);

  verifyForm: FormGroup;
  resetForm: FormGroup;

  constructor() {
    this.verifyForm = this.formBuilder.group({
      username: ['', [Validators.required]],
      secret_key: ['', [Validators.required, Validators.minLength(3)]]
    });

    this.resetForm = this.formBuilder.group({
      new_password: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(100)]],
      confirm_password: ['', [Validators.required]]
    }, { validators: this.passwordMatchValidator });
  }

  onVerifyIdentity() {
    if (this.verifyForm.invalid) {
      this.markFormGroupTouched(this.verifyForm);
      return;
    }

    this.isProcessing.set(true);
    this.error.set(null);

    const { username, secret_key } = this.verifyForm.value;

    this.authService.verifySecretKey(username, secret_key).subscribe({
      next: (response) => {
        this.isProcessing.set(false);
        if (response.success) {
          this.step.set(2);
        }
      },
      error: (err) => {
        this.isProcessing.set(false);
        const errorMessage = err.error?.message || err.error?.error || 'Verification failed';
        this.error.set(errorMessage);
      }
    });
  }

  onResetPassword() {
    if (this.resetForm.invalid) {
      this.markFormGroupTouched(this.resetForm);
      return;
    }

    this.isProcessing.set(true);
    this.error.set(null);

    const { username } = this.verifyForm.value;
    const { new_password } = this.resetForm.value;

    this.authService.resetPassword(username, new_password).subscribe({
      next: () => {
        this.isProcessing.set(false);
        this.step.set(3);
      },
      error: (err) => {
        this.isProcessing.set(false);
        const errorMessage = err.error?.message || err.error?.error || 'Password reset failed';
        this.error.set(errorMessage);
      }
    });
  }

  backToLogin() {
    this.router.navigate(['/']);
  }

  goToStep1() {
    this.step.set(1);
    this.error.set(null);
  }

  private passwordMatchValidator(control: any): { [key: string]: any } | null {
    const password = control.get('new_password');
    const confirmPassword = control.get('confirm_password');
    
    if (!password || !confirmPassword) {
      return null;
    }
    
    return password.value === confirmPassword.value ? null : { passwordsDoNotMatch: true };
  }

  private markFormGroupTouched(formGroup: FormGroup) {
    Object.keys(formGroup.controls).forEach(key => {
      formGroup.get(key)?.markAsTouched();
    });
  }
}

