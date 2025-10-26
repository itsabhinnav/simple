import { Component, signal, inject, OnInit, effect } from '@angular/core';
import { RouterOutlet, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { AuthService, User } from './services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  protected readonly title = signal('Sakura');
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private router = inject(Router);
  
  message = signal('Loading...');
  currentUser = signal<User | null>(null);
  
  ngOnInit() {
    this.http.get<any>('http://localhost:5000/health').subscribe({
      next: (data) => this.message.set(data.message),
      error: (err) => this.message.set('Backend connection failed')
    });

    // Get current auth state on init
    this.currentUser.set(this.authService.getCurrentUser());
  }

  logout() {
    this.authService.logout();
    // Force reload to landing page to ensure clean state
    window.location.href = '/';
  }
}
