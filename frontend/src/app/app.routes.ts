import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard.component';
import { UserManagementComponent } from './components/user-management.component';
import { TestCaseManagementComponent } from './components/test-case-management.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'users', component: UserManagementComponent },
  { path: 'test-cases', component: TestCaseManagementComponent },
  { path: '**', redirectTo: '' }
];
