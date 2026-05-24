import { Component, OnInit, inject, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, AbstractControl } from '@angular/forms';
import { AuthService } from '../services/auth.service';
import { RequirementService } from '../services/requirement.service';
import { TestCaseService } from '../services/test-case.service';
import { DesignTicketService, DesignTicket } from '../services/design-ticket.service';
import { Requirement } from '../services/requirement.service';
import { SpecService } from '../services/spec.service';
import { TestCase } from '../services/test-case.service';
import { TranslatePipe } from '../services/translate.pipe';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule, ReactiveFormsModule, TranslatePipe],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);
  private formBuilder = inject(FormBuilder);
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);
  private designTicketService = inject(DesignTicketService);
  private specService = inject(SpecService);

  // Local UI gates are derived from AuthService so we don't render stale state
  isAuthenticated = signal(false);
  isInitialized = signal(false);
  activeTab = signal<'login' | 'signup'>('login');
  error = signal<string | null>(null);
  isLoggingIn = signal(false);
  isSigningUp = signal(false);

  // Dashboard stats
  requirementsCount = signal(0);
  testCasesCount = signal(0);
  designTicketsCount = signal(0);
  specsCount = signal(0);
  isLoadingStats = signal(false);

  // Full lists (used to derive breakdowns)
  allRequirements = signal<Requirement[]>([]);
  allTestCases = signal<TestCase[]>([]);
  allDesignTickets = signal<DesignTicket[]>([]);

  // Recent items
  recentRequirements = signal<Requirement[]>([]);
  recentTestCases = signal<TestCase[]>([]);
  recentDesignTickets = signal<DesignTicket[]>([]);

  // Derived breakdowns for richer tile detail
  requirementPriorityBreakdown = computed(() =>
    this.countBy(this.allRequirements(), (r) => (r.priority || '').toUpperCase(), ['P1', 'P2', 'P3', 'P4'])
  );
  requirementStatusBreakdown = computed(() =>
    this.countBy(this.allRequirements(), (r) => r.status || '', ['Draft', 'Approved', 'Implemented', 'Tested', 'Closed'])
  );
  testCasePriorityBreakdown = computed(() =>
    this.countBy(this.allTestCases(), (t) => (t.priority || '').toUpperCase(), ['P1', 'P2', 'P3', 'P4'])
  );
  testCaseTypeBreakdown = computed(() =>
    this.countBy(this.allTestCases(), (t) => t.test_type || '', ['Positive', 'Negative', 'Boundary', 'Performance'])
  );
  designStatusBreakdown = computed(() =>
    this.countBy(this.allDesignTickets(), (d) => d.status || '', ['Draft', 'In Review', 'Approved', 'Implemented'])
  );

  private countBy<T>(items: T[], key: (x: T) => string, order: string[]): { key: string; count: number }[] {
    const map: Record<string, number> = {};
    for (const item of items) {
      const k = key(item);
      if (!k) continue;
      map[k] = (map[k] || 0) + 1;
    }
    const ordered = order.map((k) => ({ key: k, count: map[k] || 0 }));
    const extras = Object.keys(map)
      .filter((k) => !order.includes(k))
      .map((k) => ({ key: k, count: map[k] }));
    return [...ordered, ...extras].filter((entry) => entry.count > 0);
  }

  loginForm: FormGroup;
  signupForm: FormGroup;

  constructor() {
    // Derive auth state synchronously from AuthService (token is loaded in its ctor)
    this.isAuthenticated.set(this.authService.isAuthenticated());
    
    this.loginForm = this.formBuilder.group({
      username: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(50)]],
      password: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(100)]]
    });

        this.signupForm = this.formBuilder.group({
          username: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(50)]],
          email: ['', [Validators.required, Validators.email]],
          first_name: [''],
          last_name: [''],
          password: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(100)]],
          confirmPassword: ['', Validators.required],
          secret_key: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(50)]],
          role: ['user'] // Default role
        }, { validators: this.passwordMatchValidator });
  }

  ngOnInit() {
    // Mark initialized only after reading AuthService readiness
    this.isInitialized.set(this.authService.getIsInitialized());

    if (this.authService.isAuthenticated()) {
      this.isAuthenticated.set(true);
      this.loadDashboardStats();
    }
  }

  // Helpers so template can strictly use AuthService-backed state
  authReady(): boolean { return this.authService.getIsInitialized(); }
  authed(): boolean { return this.authService.isAuthenticated(); }

  loadDashboardStats() {
    this.isLoadingStats.set(true);
    
    // Load requirements count
    this.requirementService.getRequirements().subscribe({
      next: (requirements) => {
        this.requirementsCount.set(requirements.length);
        this.allRequirements.set(requirements);
        this.recentRequirements.set(requirements.slice(0, 5));
      },
      error: () => {
        this.requirementsCount.set(0);
        this.allRequirements.set([]);
      }
    });

    // Load test cases count
    this.testCaseService.getTestCases().subscribe({
      next: (testCases) => {
        this.testCasesCount.set(testCases.length);
        this.allTestCases.set(testCases);
        this.recentTestCases.set(testCases.slice(0, 5));
      },
      error: () => {
        this.testCasesCount.set(0);
        this.allTestCases.set([]);
      }
    });

    // Load design tickets count
    this.designTicketService.getDesignTickets().subscribe({
      next: (designTickets) => {
        this.designTicketsCount.set(designTickets.length);
        this.allDesignTickets.set(designTickets);
        this.recentDesignTickets.set(designTickets.slice(0, 5));
      },
      error: () => {
        this.designTicketsCount.set(0);
        this.allDesignTickets.set([]);
      }
    });

    // Load specifications count
    this.specService.getSpecs().subscribe({
      next: (specs) => {
        this.specsCount.set(specs.length);
        this.isLoadingStats.set(false);
      },
      error: () => {
        this.specsCount.set(0);
        this.isLoadingStats.set(false);
      }
    });
  }

  importSpecFile(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.specService.importSpecs(file).subscribe({
      next: () => this.loadDashboardStats(),
      error: (err) => console.error('Spec import failed', err)
    });
  }

  viewRequirement(req: Requirement) {
    this.router.navigate(['/requirements']);
  }

  viewTestCase(tc: TestCase) {
    this.router.navigate(['/test-cases']);
  }

  createRequirement() {
    this.router.navigate(['/requirements/create']);
  }

  createTestCase() {
    this.router.navigate(['/test-cases/create']);
  }

  createDesignTicket() {
    this.router.navigate(['/design-tickets/create']);
  }


  isAdmin(): boolean {
    const user = this.authService.getCurrentUser();
    const isAdmin = user?.role === 'admin';
    console.log('isAdmin check:', { user, role: user?.role, isAdmin });
    return isAdmin;
  }

  getCurrentUserRole(): string {
    const user = this.authService.getCurrentUser();
    return user?.role || 'none';
  }

  getCurrentUsername(): string {
    const user = this.authService.getCurrentUser();
    return user?.username || 'none';
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
      next: (response) => {
        this.isLoggingIn.set(false);
        // Update auth state
        this.isAuthenticated.set(true);
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
