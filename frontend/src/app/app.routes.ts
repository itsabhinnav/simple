import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard.component';
import { UserManagementComponent } from './components/user-management.component';
import { TestCaseManagementComponent } from './components/test-case-management.component';
import { RequirementsComponent } from './components/requirements.component';
import { ForgotPasswordComponent } from './components/forgot-password.component';
import { CreateRequirementComponent } from './components/create-requirement.component';
import { CreateTestCaseComponent } from './components/create-test-case.component';
import { RequirementDetailComponent } from './components/requirement-detail.component';
import { TestCaseDetailComponent } from './components/test-case-detail.component';
import { SplitViewComponent } from './components/split-view.component';
import { DesignTicketManagementComponent } from './components/design-ticket-management/design-ticket-management';
import { CreateDesignTicket } from './components/create-design-ticket/create-design-ticket';
import { AuthGuard } from './guards/auth.guard';
import { AdminGuard } from './guards/admin.guard';
import { SpecManagementComponent } from './components/spec-management.component';

export const routes: Routes = [
  // Authenticated dashboard
  { path: '', component: DashboardComponent, canActivate: [AuthGuard] },
  // Login route renders the same DashboardComponent (shows only login form)
  { path: 'login', component: DashboardComponent },
  { path: 'forgot-password', component: ForgotPasswordComponent },
  { path: 'requirements', component: RequirementsComponent, canActivate: [AuthGuard] },
  { path: 'requirements/create', component: CreateRequirementComponent, canActivate: [AuthGuard] },
  { path: 'requirements/:id', component: RequirementDetailComponent, canActivate: [AuthGuard] },
  { path: 'users', component: UserManagementComponent, canActivate: [AuthGuard, AdminGuard] },
  { path: 'test-cases', component: TestCaseManagementComponent, canActivate: [AuthGuard] },
  { path: 'test-cases/create', component: CreateTestCaseComponent, canActivate: [AuthGuard] },
  { path: 'test-cases/:id', component: TestCaseDetailComponent, canActivate: [AuthGuard] },
  { path: 'design-tickets', component: DesignTicketManagementComponent, canActivate: [AuthGuard] },
  { path: 'design-tickets/create', component: CreateDesignTicket, canActivate: [AuthGuard] },
  { path: 'design-tickets/:id', component: DesignTicketManagementComponent, canActivate: [AuthGuard] },
  { path: 'specs', component: SpecManagementComponent, canActivate: [AuthGuard] },
  { path: 'split-view', component: SplitViewComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '' }
];
