import { Component, OnInit, inject, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, AbstractControl } from '@angular/forms';
import { AuthService } from '../services/auth.service';
import { RequirementService } from '../services/requirement.service';
import { TestCaseService } from '../services/test-case.service';
import { Requirement } from '../services/requirement.service';
import { TestCase } from '../services/test-case.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule, ReactiveFormsModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);
  private formBuilder = inject(FormBuilder);
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);

  isAuthenticated = signal(false);
  activeTab = signal<'login' | 'signup'>('login');
  error = signal<string | null>(null);
  isLoggingIn = signal(false);
  isSigningUp = signal(false);

  // Dashboard stats
  requirementsCount = signal(0);
  testCasesCount = signal(0);
  isLoadingStats = signal(false);
  
  // Recent items
  recentRequirements = signal<Requirement[]>([]);
  recentTestCases = signal<TestCase[]>([]);

  loginForm: FormGroup;
  signupForm: FormGroup;

  constructor() {
    this.loginForm = this.formBuilder.group({
      username: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(50)]],
      password: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(100)]]
    });

        this.signupForm = this.formBuilder.group({
          username: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(50)]],
          email: ['', [Validators.required, Validators.email]],
          first_name: [''],
          last_name: [''],
          password: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(100)]],
          confirmPassword: ['', Validators.required],
          secret_key: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(50)]],
          git_token: ['', [Validators.required, Validators.minLength(10)]], // Required Git token
          role: ['user'] // Default role
        }, { validators: this.passwordMatchValidator });
  }

  ngOnInit() {
    // Set initial auth state
    this.isAuthenticated.set(this.authService.isAuthenticated());
    
    // Load stats if authenticated
    if (this.isAuthenticated()) {
      this.loadDashboardStats();
    }
  }

  loadDashboardStats() {
    this.isLoadingStats.set(true);
    
    // Load requirements count
    this.requirementService.getRequirements().subscribe({
      next: (requirements) => {
        this.requirementsCount.set(requirements.length);
        // Get recent requirements (last 5)
        const recent = requirements.slice(0, 5);
        this.recentRequirements.set(recent);
      },
      error: () => this.requirementsCount.set(0)
    });
    
    // Load test cases count
    this.testCaseService.getTestCases().subscribe({
      next: (testCases) => {
        this.testCasesCount.set(testCases.length);
        // Get recent test cases (last 5)
        const recent = testCases.slice(0, 5);
        this.recentTestCases.set(recent);
        this.isLoadingStats.set(false);
      },
      error: () => {
        this.testCasesCount.set(0);
        this.isLoadingStats.set(false);
      }
    });
  }

  viewRequirement(req: Requirement) {
    this.router.navigate(['/requirements']);
  }

  viewTestCase(tc: TestCase) {
    this.router.navigate(['/test-cases']);
  }

  createRequirement() {
    this.router.navigate(['/requirements'], { queryParams: { create: 'true' } });
  }

  createTestCase() {
    this.router.navigate(['/test-cases'], { queryParams: { create: 'true' } });
  }


  isAdmin(): boolean {
    const user = this.authService.getCurrentUser();
    return user?.role === 'admin';
  }

  showLogin() {
    this.activeTab.set('login');
    this.error.set(null);
    this.signupForm.reset();
  }

  showSignup() {
    this.activeTab.set('signup');
    this.error.set(null);
    this.loginForm.reset();
  }

  onLogin() {
    if (this.loginForm.invalid) {
      this.markFormGroupTouched(this.loginForm);
      return;
    }

    this.isLoggingIn.set(true);
    this.error.set(null);
    this.activeTab.set('login');

    this.authService.login(this.loginForm.value).subscribe({
      next: () => {
        this.isLoggingIn.set(false);
        // Reload to update auth state across the app
        window.location.href = '/';
      },
      error: (err) => {
        this.isLoggingIn.set(false);
        const errorMessage = err.error?.message || err.error?.error || 'Login failed';
        this.error.set(errorMessage);
      }
    });
  }

  onSignup() {
    if (this.signupForm.invalid) {
      this.markFormGroupTouched(this.signupForm);
      return;
    }

    this.isSigningUp.set(true);
    this.error.set(null);
    this.activeTab.set('signup');

    const signupData = {
      username: this.signupForm.value.username,
      email: this.signupForm.value.email,
      password: this.signupForm.value.password,
      first_name: this.signupForm.value.first_name || undefined,
      last_name: this.signupForm.value.last_name || undefined,
      secret_key: this.signupForm.value.secret_key,
      git_token: this.signupForm.value.git_token || undefined,
      role: this.signupForm.value.role || 'user'
    };

    this.authService.signup(signupData).subscribe({
      next: () => {
        this.isSigningUp.set(false);
        // Reload to update auth state across the app
        window.location.href = '/';
      },
      error: (err) => {
        this.isSigningUp.set(false);
        const errorMessage = err.error?.message || err.error?.error || 'Signup failed';
        this.error.set(errorMessage);
      }
    });
  }

  private passwordMatchValidator(control: AbstractControl): { [key: string]: any } | null {
    const password = control.get('password');
    const confirmPassword = control.get('confirmPassword');
    
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
