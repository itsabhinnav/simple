import { Injectable, inject } from '@angular/core';
import { CanActivate, Router, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({
  providedIn: 'root'
})
export class AuthGuard implements CanActivate {
  private authService = inject(AuthService);
  private router = inject(Router);

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): boolean {
    // When auth is globally disabled, AuthService.isAuthenticated() already
    // returns true; this branch keeps the intent explicit for readers.
    if (!this.authService.authEnabled) {
      return true;
    }

    if (this.authService.isAuthenticated()) {
      return true;
    }

    // Redirect unauthenticated users to login
    this.router.navigate(['/login']);
    return false;
  }
}

