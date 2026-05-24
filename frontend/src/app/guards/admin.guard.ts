import { Injectable, inject } from '@angular/core';
import { CanActivate, Router, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({
  providedIn: 'root'
})
export class AdminGuard implements CanActivate {
  private authService = inject(AuthService);
  private router = inject(Router);

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): boolean {
    // First check if user is authenticated. When auth is disabled,
    // AuthService.isAuthenticated() returns true via the synthetic workspace
    // user, so this still passes — but the role check below will still
    // correctly block non-admin users (including the synthetic one).
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return false;
    }

    // Then check if user is admin
    const user = this.authService.getCurrentUser();
    if (user?.role === 'admin') {
      return true;
    }

    // Non-admin users are redirected to dashboard
    this.router.navigate(['/']);
    return false;
  }
}





