import { Component, signal, inject, OnInit, effect } from '@angular/core';
import { RouterOutlet, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { AuthService, User } from './services/auth.service';
import { RequirementService } from './services/requirement.service';
import { TestCaseService } from './services/test-case.service';
import { Requirement } from './services/requirement.service';
import { TestCase } from './services/test-case.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule, RouterModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  protected readonly title = signal('Sakura');
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private router = inject(Router);
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);
  
  message = signal('Loading...');
  currentUser = signal<User | null>(null);
  
  // Search functionality
  searchQuery = signal('');
  showCreateMenu = signal(false);
  searchResults = signal<(Requirement | TestCase)[]>([]);
  
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

  onSearch(query: string) {
    this.searchQuery.set(query);
    
    if (!query.trim()) {
      this.searchResults.set([]);
      return;
    }

    // Search in both requirements and test cases
    this.requirementService.getRequirements().subscribe({
      next: (requirements) => {
        this.testCaseService.getTestCases().subscribe({
          next: (testCases) => {
            const filteredRequirements = requirements.filter(req =>
              req.title?.toLowerCase().includes(query.toLowerCase()) ||
              req.description?.toLowerCase().includes(query.toLowerCase()) ||
              req.requirement_id?.toLowerCase().includes(query.toLowerCase())
            );
            
            const filteredTestCases = testCases.filter(tc =>
              tc.test_case_id?.toLowerCase().includes(query.toLowerCase()) ||
              tc.test_objective?.toLowerCase().includes(query.toLowerCase()) ||
              tc.feature?.toLowerCase().includes(query.toLowerCase())
            );
            
            this.searchResults.set([...filteredRequirements, ...filteredTestCases]);
          }
        });
      }
    });
  }

  toggleCreateMenu() {
    this.showCreateMenu.set(!this.showCreateMenu());
  }

  closeCreateMenu() {
    this.showCreateMenu.set(false);
  }

  createRequirement() {
    this.router.navigate(['/requirements/create']);
    this.closeCreateMenu();
  }

  createTestCase() {
    this.router.navigate(['/test-cases/create']);
    this.closeCreateMenu();
  }
}
