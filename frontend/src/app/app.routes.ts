import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard.component';
import { UserManagementComponent } from './components/user-management.component';
import { TestCaseManagementComponent } from './components/test-case-management.component';
import { ForgotPasswordComponent } from './components/forgot-password.component';
import { AuthGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'forgot-password', component: ForgotPasswordComponent },
  { path: 'users', component: UserManagementComponent, canActivate: [AuthGuard] },
  { path: 'test-cases', component: TestCaseManagementComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '' }
];
