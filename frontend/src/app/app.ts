import { Component, signal, inject, OnInit, effect, HostListener } from '@angular/core';
import { RouterOutlet, Router, RouterModule, NavigationEnd } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { AuthService, User } from './services/auth.service';
import { RequirementService } from './services/requirement.service';
import { TestCaseService } from './services/test-case.service';
import { Requirement } from './services/requirement.service';
import { TestCase } from './services/test-case.service';
import { TranslationService } from './services/translation.service';
import { TranslatePipe } from './services/translate.pipe';
import { AutoTranslateDirective } from './services/auto-translate.directive';
import { API_BASE } from './app-settings';
import { filter } from 'rxjs/operators';

function scrollAppToTop(): void {
  if (typeof window === 'undefined') return;
  window.scrollTo(0, 0);
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule, RouterModule, TranslatePipe, AutoTranslateDirective],
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
  translationService = inject(TranslationService);

  /** Mirror of AuthService.authEnabled so templates can hide login/logout UI. */
  protected readonly authEnabled = this.authService.authEnabled;
  
  message = signal('Loading...');
  currentUser = signal<User | null>(null);
  isInitialized = signal(false);
  
  // Search functionality
  searchQuery = signal('');
  showCreateMenu = signal(false);
  showLangMenu = signal(false);
  searchResults = signal<(Requirement | TestCase)[]>([]);
  showSearchResults = signal(true);
  
  constructor() {
    // Sync with AuthService currentUser changes (reactive)
    effect(() => {
      const user = this.authService.getCurrentUser();
      this.currentUser.set(user);
    });

    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd)
    ).subscribe(() => {
      queueMicrotask(() => scrollAppToTop());
    });
  }
  
  ngOnInit() {
    this.http.get<any>(`${API_BASE}/health`).subscribe({
      next: (data) => this.message.set(data.message),
      error: (err) => this.message.set('Backend connection failed')
    });

    // Get current auth state on init
    this.currentUser.set(this.authService.getCurrentUser());
    
    // Mark as initialized to prevent flash
    setTimeout(() => {
      this.isInitialized.set(true);
    }, 0);
  }

  logout() {
    this.authService.logout();
    // Force reload to landing page to ensure clean state
    window.location.href = '/';
  }

  onSearch(query: string) {
    this.searchQuery.set(query);
    this.showSearchResults.set(true);
    
    if (!query.trim()) {
      this.searchResults.set([]);
      return;
    }

    this.requirementService.getRequirements().subscribe({
      next: (requirements) => {
        const filteredRequirements = requirements.filter(req =>
          req.title?.toLowerCase().includes(query.toLowerCase()) ||
          req.description?.toLowerCase().includes(query.toLowerCase()) ||
          req.requirement_id?.toLowerCase().includes(query.toLowerCase())
        );
        
        this.testCaseService.getTestCases().subscribe({
          next: (testCases) => {
            const filteredTestCases = testCases.filter(tc =>
              tc.test_case_id?.toLowerCase().includes(query.toLowerCase()) ||
              tc.test_objective?.toLowerCase().includes(query.toLowerCase()) ||
              TestCaseService.mvDisplay(tc.feature).toLowerCase().includes(query.toLowerCase())
            );
            
            this.searchResults.set([...filteredRequirements, ...filteredTestCases]);
          },
          error: (err) => {
            console.error('Error loading test cases:', err);
            this.searchResults.set(filteredRequirements);
          }
        });
      },
      error: (err) => {
        console.error('Error loading requirements:', err);
        this.searchResults.set([]);
      }
    });
  }

  handleSearchBlur(event: FocusEvent) {
    // Delay hiding to allow clicking on results
    const target = event.relatedTarget as HTMLElement;
    
    // Check if the blur is moving to a search result
    if (target && target.closest('.search-results-dropdown')) {
      return; // Don't hide if clicking on results
    }
    
    setTimeout(() => {
      this.showSearchResults.set(false);
    }, 150);
  }

  handleSearchFocus() {
    this.showSearchResults.set(true);
  }

  navigateToItem(item: Requirement | TestCase, event: Event) {
    event.preventDefault();
    event.stopPropagation();
    
    if ('requirement_id' in item) {
      this.router.navigate(['/requirements', item.requirement_id]);
    } else if ('test_case_id' in item) {
      this.router.navigate(['/test-cases', item.test_case_id]);
    }
    this.searchQuery.set('');
    this.searchResults.set([]);
    this.showSearchResults.set(false);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    const target = event.target as HTMLElement | null;
    if (!target) return;
    if (this.showCreateMenu() && !target.closest('.create-container-header')) {
      this.showCreateMenu.set(false);
    }
    if (this.showLangMenu() && !target.closest('.lang-container')) {
      this.showLangMenu.set(false);
    }
  }

  @HostListener('document:keydown.escape')
  onEscapeKey() {
    this.showCreateMenu.set(false);
    this.showLangMenu.set(false);
  }

  toggleCreateMenu() {
    this.showCreateMenu.set(!this.showCreateMenu());
    this.showLangMenu.set(false);
  }

  closeCreateMenu() {
    this.showCreateMenu.set(false);
  }

  toggleLangMenu() {
    this.showLangMenu.set(!this.showLangMenu());
    this.showCreateMenu.set(false);
  }

  setLanguage(lang: 'en' | 'ja') {
    this.translationService.setLanguage(lang);
    this.showLangMenu.set(false);
  }

  createRequirement() {
    this.router.navigate(['/requirements/create']);
    this.closeCreateMenu();
  }

  createTestCase() {
    this.router.navigate(['/test-cases/create']);
    this.closeCreateMenu();
  }

  isAdmin(): boolean {
    return this.currentUser()?.role === 'admin';
  }

  isDashboardPage(): boolean {
    // Use Angular's Router instead of window.location so this also works during
    // server-side prerender (where `window` is undefined).
    const url = this.router.url.split('?')[0].split('#')[0];
    return url === '/' || url === '';
  }
}
