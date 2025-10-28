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
import { AuthGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'forgot-password', component: ForgotPasswordComponent },
  { path: 'requirements', component: RequirementsComponent, canActivate: [AuthGuard] },
  { path: 'requirements/create', component: CreateRequirementComponent, canActivate: [AuthGuard] },
  { path: 'requirements/:id', component: RequirementDetailComponent, canActivate: [AuthGuard] },
  { path: 'users', component: UserManagementComponent, canActivate: [AuthGuard] },
  { path: 'test-cases', component: TestCaseManagementComponent, canActivate: [AuthGuard] },
  { path: 'test-cases/create', component: CreateTestCaseComponent, canActivate: [AuthGuard] },
  { path: 'test-cases/:id', component: TestCaseDetailComponent, canActivate: [AuthGuard] },
  { path: 'split-view', component: SplitViewComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '' }
];
