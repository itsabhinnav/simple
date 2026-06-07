import { Component, OnInit, inject, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, AbstractControl } from '@angular/forms';
import { AuthService } from '../services/auth.service';
import { RequirementService } from '../services/requirement.service';
import { TestCase, TestCaseService } from '../services/test-case.service';
import { DesignTicketService, DesignTicket } from '../services/design-ticket.service';
import { Requirement } from '../services/requirement.service';
import { SpecService } from '../services/spec.service';
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

  // ---------- Aggregate KPIs ----------
  totalAssets = computed(() =>
    this.requirementsCount() + this.testCasesCount() + this.designTicketsCount() + this.specsCount()
  );

  /** % of requirements covered by at least one linked test case (via associated_requirement_id). */
  coveragePercent = computed(() => {
    const reqs = this.allRequirements();
    if (reqs.length === 0) return 0;
    const covered = new Set<string>();
    for (const tc of this.allTestCases()) {
      for (const id of TestCaseService.mvArray(tc.associated_requirement_id)) {
        covered.add(id);
      }
    }
    let n = 0;
    for (const r of reqs) if (covered.has(r.requirement_id)) n++;
    return Math.round((n / reqs.length) * 100);
  });

  /** Number of requirements linked downstream to at least one design. */
  designLinkedPercent = computed(() => {
    const reqs = this.allRequirements();
    if (reqs.length === 0) return 0;
    const linked = new Set<string>();
    for (const d of this.allDesignTickets()) {
      if (d.linked_requirement_id) linked.add(d.linked_requirement_id);
    }
    let n = 0;
    for (const r of reqs) if (linked.has(r.requirement_id)) n++;
    return Math.round((n / reqs.length) * 100);
  });

  /** Composite project-health score (0–100) blending workflow progress and coverage. */
  qualityScore = computed(() => {
    const reqs = this.allRequirements();
    const designs = this.allDesignTickets();
    let score = 0, weight = 0;
    if (reqs.length > 0) {
      const advanced = reqs.filter(r => ['Approved','Implemented','Tested','Closed'].includes(r.status || '')).length;
      score += (advanced / reqs.length) * 40; weight += 40;
    }
    if (designs.length > 0) {
      const advanced = designs.filter(d => ['Approved','Implemented'].includes(d.status || '')).length;
      score += (advanced / designs.length) * 30; weight += 30;
    }
    score += (this.coveragePercent() / 100) * 30; weight += 30;
    return weight > 0 ? Math.round((score / weight) * 100) : 0;
  });

  // ---------- Donut & bar segment helpers ----------
  private static REQ_STATUS_COLORS: Record<string, string> = {
    Draft: '#94a3b8', Approved: '#10b981', Implemented: '#3b82f6', Tested: '#8b5cf6', Closed: '#475569',
  };
  private static DESIGN_STATUS_COLORS: Record<string, string> = {
    Draft: '#94a3b8', 'In Review': '#f59e0b', Approved: '#10b981', Implemented: '#3b82f6',
  };
  private static TEST_TYPE_COLORS: Record<string, string> = {
    Positive: '#10b981', Negative: '#ef4444', Boundary: '#f59e0b', Performance: '#3b82f6', Abnormal: '#a855f7',
  };
  private static PRIORITY_COLORS: Record<string, string> = {
    P1: '#dc2626', P2: '#ea580c', P3: '#ca8a04', P4: '#16a34a',
  };

  private static DONUT_R = 42;
  private static DONUT_C = 2 * Math.PI * 42;

  private toDonutSegments(rows: { key: string; count: number }[], palette: Record<string, string>) {
    const total = rows.reduce((s, r) => s + r.count, 0);
    if (total === 0) return [] as { label: string; count: number; percent: number; color: string; length: number; offset: number }[];
    let cum = 0;
    return rows.filter(r => r.count > 0).map(r => {
      const length = (r.count / total) * DashboardComponent.DONUT_C;
      const seg = {
        label: r.key,
        count: r.count,
        percent: Math.round((r.count / total) * 100),
        color: palette[r.key] || '#94a3b8',
        length,
        offset: -cum,
      };
      cum += length;
      return seg;
    });
  }

  donutCircumference = DashboardComponent.DONUT_C;

  testTypeDonut = computed(() =>
    this.toDonutSegments(this.testCaseTypeBreakdown(), DashboardComponent.TEST_TYPE_COLORS)
  );
  requirementStatusDonut = computed(() =>
    this.toDonutSegments(this.requirementStatusBreakdown(), DashboardComponent.REQ_STATUS_COLORS)
  );
  designStatusDonut = computed(() =>
    this.toDonutSegments(this.designStatusBreakdown(), DashboardComponent.DESIGN_STATUS_COLORS)
  );

  /** Stacked horizontal bar segments for an entity's status breakdown. */
  private toStackBar(rows: { key: string; count: number }[], palette: Record<string, string>) {
    const total = rows.reduce((s, r) => s + r.count, 0);
    if (total === 0) return [] as { label: string; count: number; percent: number; color: string }[];
    return rows.filter(r => r.count > 0).map(r => ({
      label: r.key,
      count: r.count,
      percent: Math.round((r.count / total) * 100),
      color: palette[r.key] || '#94a3b8',
    }));
  }

  requirementStatusBar = computed(() =>
    this.toStackBar(this.requirementStatusBreakdown(), DashboardComponent.REQ_STATUS_COLORS)
  );
  designStatusBar = computed(() =>
    this.toStackBar(this.designStatusBreakdown(), DashboardComponent.DESIGN_STATUS_COLORS)
  );
  testTypeBar = computed(() =>
    this.toStackBar(this.testCaseTypeBreakdown(), DashboardComponent.TEST_TYPE_COLORS)
  );

  /** Priority distribution merged across requirements + test cases for the bar widget. */
  priorityDistribution = computed(() => {
    const order = ['P1', 'P2', 'P3', 'P4'];
    const map: Record<string, { req: number; test: number }> =
      Object.fromEntries(order.map(k => [k, { req: 0, test: 0 }]));
    for (const r of this.allRequirements()) {
      const p = (r.priority || '').toUpperCase();
      if (map[p]) map[p].req++;
    }
    for (const t of this.allTestCases()) {
      const p = (t.priority || '').toUpperCase();
      if (map[p]) map[p].test++;
    }
    const maxVal = Math.max(1, ...order.flatMap(k => [map[k].req, map[k].test]));
    return order.map(key => ({
      key,
      req: map[key].req,
      test: map[key].test,
      reqWidth: Math.round((map[key].req / maxVal) * 100),
      testWidth: Math.round((map[key].test / maxVal) * 100),
      color: DashboardComponent.PRIORITY_COLORS[key],
    }));
  });

  /** Combined recent activity timeline across requirements / tests / designs, newest first. */
  combinedActivity = computed(() => {
    const items: { kind: 'requirement' | 'test' | 'design'; icon: string; id: string; title: string; meta: string; ts: number; route: string; color: string }[] = [];
    for (const r of this.recentRequirements()) {
      const ts = r.created_at ? new Date(r.created_at).getTime() : 0;
      items.push({ kind: 'requirement', icon: '📋', id: r.requirement_id, title: r.title || '(untitled)', meta: r.status || r.priority || '', ts, route: '/requirements', color: '#3b82f6' });
    }
    for (const t of this.recentTestCases()) {
      const ts = t.created_at ? new Date(t.created_at).getTime() : 0;
      items.push({ kind: 'test', icon: '🧪', id: t.test_case_id, title: t.title || t.test_objective || '(untitled)', meta: t.test_type || t.priority || '', ts, route: '/test-cases', color: '#10b981' });
    }
    for (const d of this.recentDesignTickets()) {
      const ts = d.created_at ? new Date(d.created_at).getTime() : 0;
      items.push({ kind: 'design', icon: '🎨', id: d.design_ticket_id, title: d.title || '(untitled)', meta: d.status || d.priority || '', ts, route: '/design-tickets', color: '#f59e0b' });
    }
    return items.sort((a, b) => b.ts - a.ts).slice(0, 6);
  });

  /** Human-friendly relative time for the activity feed. */
  formatRelativeTime(ts: number): string {
    if (!ts) return '';
    const diffMs = Date.now() - ts;
    const m = Math.round(diffMs / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.round(h / 24);
    if (d < 30) return `${d}d ago`;
    const mo = Math.round(d / 30);
    if (mo < 12) return `${mo}mo ago`;
    return `${Math.round(mo / 12)}y ago`;
  }

  /** Tier label for the quality gauge (drives the gauge color). */
  qualityTier = computed<'low' | 'mid' | 'high'>(() => {
    const s = this.qualityScore();
    if (s >= 75) return 'high';
    if (s >= 45) return 'mid';
    return 'low';
  });

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
