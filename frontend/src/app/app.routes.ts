import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard.component';
import { UserManagementComponent } from './components/user-management.component';
import { TestCaseManagementComponent } from './components/test-case-management.component';
import { RequirementsComponent } from './components/requirements.component';
import { ForgotPasswordComponent } from './components/forgot-password.component';
import { CreateRequirementComponent } from './components/create-requirement.component';
import { CreateTestCaseComponent } from './components/create-test-case.component';
import { ImportTestCasesComponent } from './components/import-test-cases.component';
import { SmartImportComponent } from './components/smart-import.component';
import { RequirementDetailComponent } from './components/requirement-detail.component';
import { TestCaseDetailComponent } from './components/test-case-detail.component';
import { SplitViewComponent } from './components/split-view.component';
import { DesignTicketManagementComponent } from './components/design-ticket-management/design-ticket-management';
import { CreateDesignTicket } from './components/create-design-ticket/create-design-ticket';
import { AuthGuard } from './guards/auth.guard';
import { AdminGuard } from './guards/admin.guard';
import { SpecManagementComponent } from './components/spec-management.component';
import { SpecProjectDetailComponent } from './components/spec-project-detail.component';
import { AdminSettingsComponent } from './components/admin-settings.component';
import { AssistantComponent } from './components/assistant.component';
import { APP_SETTINGS } from './app-settings';

// When auth is disabled, /login and /forgot-password are meaningless. Redirect
// them to the dashboard so users (or bookmarks/links) don't land on inert
// auth screens.
const loginRoute = APP_SETTINGS.auth.enabled
  ? { path: 'login', component: DashboardComponent }
  : { path: 'login', redirectTo: '', pathMatch: 'full' as const };

const forgotPasswordRoute = APP_SETTINGS.auth.enabled
  ? { path: 'forgot-password', component: ForgotPasswordComponent }
  : { path: 'forgot-password', redirectTo: '', pathMatch: 'full' as const };

export const routes: Routes = [
  // Authenticated dashboard
  { path: '', component: DashboardComponent, canActivate: [AuthGuard] },
  loginRoute,
  forgotPasswordRoute,
  { path: 'requirements', component: RequirementsComponent, canActivate: [AuthGuard] },
  { path: 'requirements/create', component: CreateRequirementComponent, canActivate: [AuthGuard] },
  // Smart Import wizard — generic, target driven via route data. Uses
  // the new robust hybrid parsing API (/api/parsing/*) for AI-driven
  // enrichment and the existing deterministic /import endpoints for
  // the actual DB write. The legacy /test-cases/import route below
  // continues to serve the original test-case-only component for
  // backwards compatibility with bookmarks.
  { path: 'requirements/import', component: SmartImportComponent, canActivate: [AuthGuard], data: { target: 'requirements' } },
  { path: 'requirements/:id', component: RequirementDetailComponent, canActivate: [AuthGuard] },
  { path: 'users', component: UserManagementComponent, canActivate: [AuthGuard, AdminGuard] },
  { path: 'admin/settings', component: AdminSettingsComponent, canActivate: [AuthGuard, AdminGuard] },
  { path: 'test-cases', component: TestCaseManagementComponent, canActivate: [AuthGuard] },
  { path: 'test-cases/create', component: CreateTestCaseComponent, canActivate: [AuthGuard] },
  { path: 'test-cases/import', component: SmartImportComponent, canActivate: [AuthGuard], data: { target: 'test_cases' } },
  { path: 'test-cases/import/legacy', component: ImportTestCasesComponent, canActivate: [AuthGuard] },
  { path: 'test-cases/:id', component: TestCaseDetailComponent, canActivate: [AuthGuard] },
  { path: 'design-tickets', component: DesignTicketManagementComponent, canActivate: [AuthGuard] },
  { path: 'design-tickets/create', component: CreateDesignTicket, canActivate: [AuthGuard] },
  { path: 'design-tickets/import', component: SmartImportComponent, canActivate: [AuthGuard], data: { target: 'design_tickets' } },
  { path: 'design-tickets/:id', component: DesignTicketManagementComponent, canActivate: [AuthGuard] },
  { path: 'specs', component: SpecManagementComponent, canActivate: [AuthGuard] },
  { path: 'specs/project/:project', component: SpecProjectDetailComponent, canActivate: [AuthGuard] },
  { path: 'specs/import', component: SmartImportComponent, canActivate: [AuthGuard], data: { target: 'specifications' } },
  { path: 'split-view', component: SplitViewComponent, canActivate: [AuthGuard] },
  { path: 'assistant', component: AssistantComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '' }
];
