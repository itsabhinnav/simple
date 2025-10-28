import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { RequirementService, Requirement } from '../services/requirement.service';
import { TestCaseService, TestCase } from '../services/test-case.service';

@Component({
  selector: 'app-split-view',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="split-view-container">
      <!-- Header -->
      <header class="management-header">
        <div class="header-left">
          <nav class="breadcrumb">
            <a routerLink="/" class="breadcrumb-link">
              <i class="icon-database"></i>
              Dashboard
            </a>
            <span class="breadcrumb-separator">›</span>
            <span class="breadcrumb-current">Requirements & Test Cases</span>
          </nav>
          <h1 class="page-title">
            <i class="icon-view"></i>
            Split View
          </h1>
        </div>
        <div class="header-actions">
          <button class="view-btn" [class.active]="viewType === 'requirements'" (click)="viewType = 'requirements'">
            Requirements
          </button>
          <button class="view-btn" [class.active]="viewType === 'test-cases'" (click)="viewType = 'test-cases'">
            Test Cases
          </button>
        </div>
      </header>

      <!-- Split Content -->
      <div class="split-content">
        <!-- Left Panel - List View -->
        <div class="list-panel">
          <div class="list-header">
              <h3>{{ viewType === 'requirements' ? 'Requirements' : 'Test Cases' }} ({{ viewType === 'requirements' ? filteredRequirements().length : filteredTestCases().length }})</h3>
            <input 
              type="text" 
              placeholder="Search..." 
              [ngModel]="searchTerm()"
              (ngModelChange)="searchTerm.set($event)"
              class="search-input">
          </div>
          
          <div class="list-items" *ngIf="viewType === 'requirements'">
            <div 
              *ngFor="let req of filteredRequirements()" 
              class="list-item"
              [class.active]="selectedRequirement()?.id === req.id"
              (click)="selectRequirement(req)">
              <div class="item-id">{{ req.requirement_id }}</div>
              <div class="item-title">{{ req.title }}</div>
              <div class="item-meta">
                <span class="badge" [class]="getPriorityClass(req.priority)">{{ req.priority }}</span>
                <span class="badge" [class]="getStatusClass(req.status)">{{ req.status }}</span>
              </div>
            </div>
          </div>

          <div class="list-items" *ngIf="viewType === 'test-cases'">
            <div 
              *ngFor="let tc of filteredTestCases()" 
              class="list-item"
              [class.active]="selectedTestCase()?.test_case_id === tc.test_case_id"
              (click)="selectTestCase(tc)">
              <div class="item-id">{{ tc.test_case_id }}</div>
              <div class="item-title">{{ tc.test_objective || 'Test Case' }}</div>
              <div class="item-meta">
                <span class="badge" [class]="getPriorityClass(tc.priority)">{{ tc.priority || 'P3' }}</span>
                <span class="badge" [class]="getTypeClass(tc.test_type)">{{ tc.test_type || 'N/A' }}</span>
              </div>
            </div>
          </div>

          <div *ngIf="(viewType === 'requirements' ? filteredRequirements().length : filteredTestCases().length) === 0" class="empty-state">
            <p>No {{ viewType === 'requirements' ? 'requirements' : 'test cases' }} found</p>
          </div>
        </div>

        <!-- Right Panel - Detail View -->
        <div class="detail-panel">
          <!-- Empty State when no item selected -->
          <div *ngIf="(viewType === 'requirements' && !selectedRequirement()) || (viewType === 'test-cases' && !selectedTestCase())" class="empty-detail-state">
            <i class="icon-empty"></i>
            <h3>No item selected</h3>
            <p>Select an item from the list to view its details</p>
          </div>
          
          <!-- Requirement Detail -->
          <div *ngIf="viewType === 'requirements' && selectedRequirement()" class="detail-content">
            <div class="detail-card">
              <div class="card-header">
                <div class="header-top">
                  <div class="title-group">
                    <h2 class="card-title">{{ selectedRequirement()!.title }}</h2>
                    <span class="req-id">{{ selectedRequirement()!.requirement_id }}</span>
                  </div>
                  <div class="badges-group">
                    <span class="priority-badge" [class]="getPriorityClass(selectedRequirement()!.priority)">
                      {{ selectedRequirement()!.priority }}
                    </span>
                    <span class="status-badge" [class]="getStatusClass(selectedRequirement()!.status)">
                      {{ selectedRequirement()!.status }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="card-body">
                <div class="detail-section" *ngIf="selectedRequirement()!.description">
                  <h3 class="section-title">Description</h3>
                  <p class="section-content">{{ selectedRequirement()!.description }}</p>
                </div>

                <div class="detail-meta">
                  <div class="meta-item" *ngIf="selectedRequirement()!.requirement_type">
                    <span class="meta-label">Type:</span>
                    <span class="meta-value">{{ selectedRequirement()!.requirement_type }}</span>
                  </div>
                  <div class="meta-item" *ngIf="selectedRequirement()!.assignee">
                    <span class="meta-label">Assignee:</span>
                    <span class="meta-value">{{ selectedRequirement()!.assignee }}</span>
                  </div>
                  <div class="meta-item" *ngIf="selectedRequirement()!.tags">
                    <span class="meta-label">Tags:</span>
                    <span class="meta-value">{{ selectedRequirement()!.tags }}</span>
                  </div>
                  <div class="meta-item" *ngIf="selectedRequirement()!.created_at">
                    <span class="meta-label">Created:</span>
                    <span class="meta-value">{{ selectedRequirement()!.created_at }}</span>
                  </div>
                  <div class="meta-item" *ngIf="selectedRequirement()!.updated_at">
                    <span class="meta-label">Updated:</span>
                    <span class="meta-value">{{ selectedRequirement()!.updated_at }}</span>
                  </div>
                </div>

                <div class="detail-actions">
                  <button class="btn-primary" (click)="viewRequirementDetail(selectedRequirement()!.id!)">
                    View Full Details
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Test Case Detail -->
          <div *ngIf="viewType === 'test-cases' && selectedTestCase()" class="detail-content">
            <div class="detail-card">
              <div class="card-header">
                <div class="header-top">
                  <div class="title-group">
                    <h2 class="card-title">{{ selectedTestCase()!.test_objective || 'Test Case' }}</h2>
                    <span class="req-id">{{ selectedTestCase()!.test_case_id }}</span>
                  </div>
                  <div class="badges-group">
                    <span class="priority-badge" [class]="getPriorityClass(selectedTestCase()!.priority || '')" *ngIf="selectedTestCase()!.priority">
                      {{ selectedTestCase()!.priority }}
                    </span>
                    <span class="status-badge" [class]="getTypeClass(selectedTestCase()!.test_type || '')" *ngIf="selectedTestCase()!.test_type">
                      {{ selectedTestCase()!.test_type }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="card-body">
                <div class="detail-section" *ngIf="selectedTestCase()!.preconditions">
                  <h3 class="section-title">Preconditions</h3>
                  <p class="section-content">{{ selectedTestCase()!.preconditions }}</p>
                </div>

                <div class="detail-section" *ngIf="selectedTestCase()!.procedure">
                  <h3 class="section-title">Procedure</h3>
                  <p class="section-content">{{ selectedTestCase()!.procedure }}</p>
                </div>

                <div class="detail-section" *ngIf="selectedTestCase()!.expected_behavior">
                  <h3 class="section-title">Expected Behavior</h3>
                  <p class="section-content">{{ selectedTestCase()!.expected_behavior }}</p>
                </div>

                <div class="detail-meta">
                  <div class="meta-item" *ngIf="selectedTestCase()!.feature">
                    <span class="meta-label">Feature:</span>
                    <span class="meta-value">{{ selectedTestCase()!.feature }}</span>
                  </div>
                  <div class="meta-item" *ngIf="selectedTestCase()!.screen_id">
                    <span class="meta-label">Screen ID:</span>
                    <span class="meta-value">{{ selectedTestCase()!.screen_id }}</span>
                  </div>
                  <div class="meta-item" *ngIf="selectedTestCase()!.associated_requirement_id">
                    <span class="meta-label">Requirement ID:</span>
                    <span class="meta-value">{{ selectedTestCase()!.associated_requirement_id }}</span>
                  </div>
                  <div class="meta-item" *ngIf="selectedTestCase()!.region">
                    <span class="meta-label">Region:</span>
                    <span class="meta-value">{{ selectedTestCase()!.region }}</span>
                  </div>
                </div>

                <div class="detail-actions">
                  <button class="btn-primary" (click)="viewTestCaseDetail(selectedTestCase()!.test_case_id!)">
                    View Full Details
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div *ngIf="!getSelectedItem()" class="empty-detail">
            <div class="empty-state-large">
              <i class="icon-empty">📋</i>
              <h3>Select an item</h3>
              <p>Choose a {{ viewType === 'requirements' ? 'requirement' : 'test case' }} from the list to view details</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .split-view-container {
      height: calc(100vh - 100px);
      display: flex;
      flex-direction: column;
      padding: 20px;
    }

    .management-header {
      background-color: white;
      border: 1px solid #dadce0;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .header-left {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .breadcrumb {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }

    .breadcrumb-link {
      color: #5f6368;
      text-decoration: none;
      transition: color 0.2s;
    }

    .breadcrumb-link:hover {
      color: #202124;
    }

    .breadcrumb-separator {
      color: #5f6368;
    }

    .breadcrumb-current {
      color: #202124;
      font-weight: 500;
    }

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .header-actions {
      display: flex;
      gap: 8px;
    }

    .view-btn {
      padding: 10px 20px;
      border: 1px solid #dadce0;
      border-radius: 24px;
      background: white;
      color: #5f6368;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }

    .view-btn:hover {
      border-color: #1a73e8;
      color: #1a73e8;
    }

    .view-btn.active {
      background: #1a73e8;
      color: white;
      border-color: #1a73e8;
    }

    .split-content {
      display: grid;
      grid-template-columns: 450px 1fr;
      gap: 20px;
      flex: 1;
      overflow: hidden;
      border: 1px solid #dadce0;
      border-radius: 8px;
      background: #f5f5f5;
      padding: 20px;
    }

    .list-panel {
      background: white;
      border: 2px solid #333;
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    .list-header {
      padding: 16px;
      border-bottom: 2px solid #dadce0;
      background: white;
      margin: 0;
    }

    .list-header h3 {
      margin: 0 0 12px 0;
      font-size: 16px;
      font-weight: 600;
    }

    .list-items {
      padding: 8px 0;
      overflow-y: auto;
      flex: 1;
    }

    .search-input {
      width: 100%;
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 6px;
      font-size: 14px;
    }

    .list-items {
      padding: 8px 0;
      overflow-y: auto;
      flex: 1;
    }

    .list-item {
      padding: 16px;
      border: 1px solid #dadce0;
      cursor: pointer;
      transition: all 0.2s;
      background: white;
      margin-bottom: 8px;
      border-radius: 6px;
      margin-left: 8px;
      margin-right: 8px;
    }

    .list-item:hover {
      background: #f5f5f5;
      border-color: #1a73e8;
    }

    .list-item.active {
      background: #e8f0fe;
      border: 2px solid #1a73e8;
      box-shadow: 0 2px 4px rgba(26, 115, 232, 0.2);
    }

    .item-id {
      font-weight: 600;
      color: #1a73e8;
      font-size: 13px;
      margin-bottom: 6px;
    }

    .item-title {
      font-size: 15px;
      color: #333;
      margin-bottom: 10px;
      line-height: 1.5;
      font-weight: 500;
    }

    .item-meta {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
    }

    .badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 500;
    }

    .detail-panel {
      background: white;
      border: 2px solid #333;
      border-radius: 8px;
      overflow-y: auto;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    .detail-card {
      width: 100%;
    }

    .card-header {
      margin-bottom: 24px;
    }

    .header-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }

    .title-group {
      flex: 1;
    }

    .card-title {
      margin: 0 0 8px 0;
      font-size: 24px;
      font-weight: 600;
      color: #202124;
    }

    .req-id {
      display: inline-block;
      padding: 4px 12px;
      background: #f0f0f0;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
      color: #5f6368;
    }

    .badges-group {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .priority-badge, .status-badge {
      padding: 6px 12px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 500;
    }

    .card-body {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .detail-section {
      margin-bottom: 20px;
    }

    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: #5f6368;
      margin: 0 0 8px 0;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .section-content {
      font-size: 15px;
      color: #202124;
      line-height: 1.6;
      margin: 0;
    }

    .detail-meta {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      padding: 16px;
      background: #f9f9f9;
      border-radius: 8px;
    }

    .meta-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .meta-label {
      font-size: 12px;
      color: #5f6368;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .meta-value {
      font-size: 14px;
      color: #202124;
    }

    .detail-actions {
      margin-top: 20px;
      padding-top: 20px;
      border-top: 1px solid #e0e0e0;
    }

    .btn-primary {
      padding: 10px 20px;
      background: #1a73e8;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
    }

    .btn-primary:hover {
      background: #1557b0;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    .empty-state {
      padding: 40px;
      text-align: center;
      color: #999;
    }

    .empty-detail-state {
      padding: 60px 40px;
      text-align: center;
      color: #999;
    }

    .empty-detail-state i {
      font-size: 48px;
      margin-bottom: 16px;
      opacity: 0.3;
    }

    .empty-detail-state h3 {
      margin: 0 0 8px 0;
      color: #5f6368;
    }

    .empty-detail-state p {
      margin: 0;
      color: #999;
    }

    .empty-detail {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .empty-state-large {
      text-align: center;
      color: #999;
    }

    .empty-state-large i {
      font-size: 48px;
      margin-bottom: 16px;
    }

    .empty-state-large h3 {
      margin: 0 0 8px 0;
      color: #5f6368;
    }

    .empty-state-large p {
      margin: 0;
      color: #999;
    }

    .priority-p1, .priority-critical { background: #ffebee; color: #c62828; }
    .priority-p2, .priority-high { background: #fff3e0; color: #ef6c00; }
    .priority-p3, .priority-medium { background: #e8f5e8; color: #2e7d32; }
    .priority-p4, .priority-low { background: #e3f2fd; color: #1976d2; }
    .priority-default { background: #f5f5f5; color: #757575; }

    .status-draft { background: #f5f5f5; color: #757575; }
    .status-active { background: #e3f2fd; color: #1976d2; }
    .status-progress { background: #fff3e0; color: #f57c00; }
    .status-review { background: #f3e5f5; color: #7b1fa2; }
    .status-completed { background: #e8f5e8; color: #2e7d32; }

    .icon-database::before { content: "📊"; }
    .icon-view::before { content: "👁️"; }
  `]
})
export class SplitViewComponent implements OnInit {
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);
  private router = inject(Router);

  requirements = signal<Requirement[]>([]);
  testCases = signal<TestCase[]>([]);
  selectedRequirement = signal<Requirement | null>(null);
  selectedTestCase = signal<TestCase | null>(null);
  searchTerm = signal('');
  viewType: 'requirements' | 'test-cases' = 'requirements';
  
  // Computed signals for filtered results
  filteredRequirements = computed(() => {
    const term = this.searchTerm().toLowerCase();
    return this.requirements().filter(r => 
      r.title.toLowerCase().includes(term) ||
      r.requirement_id.toLowerCase().includes(term) ||
      (r.description && r.description.toLowerCase().includes(term))
    );
  });
  
  filteredTestCases = computed(() => {
    const term = this.searchTerm().toLowerCase();
    return this.testCases().filter(tc => 
      (tc.test_case_id && tc.test_case_id.toLowerCase().includes(term)) ||
      (tc.test_objective && tc.test_objective.toLowerCase().includes(term)) ||
      (tc.feature && tc.feature.toLowerCase().includes(term))
    );
  });

  ngOnInit() {
    this.loadRequirements();
    this.loadTestCases();
  }

  loadRequirements() {
    this.requirementService.getRequirements().subscribe({
      next: (reqs) => {
        this.requirements.set(reqs || []);
        // Auto-select first requirement when requirements load
        if (this.viewType === 'requirements' && reqs && reqs.length > 0 && !this.selectedRequirement()) {
          this.selectRequirement(reqs[0]);
        }
      },
      error: () => {}
    });
  }

  loadTestCases() {
    this.testCaseService.getTestCases().subscribe({
      next: (tcs) => {
        this.testCases.set(tcs || []);
        // Auto-select first test case when test cases load
        if (this.viewType === 'test-cases' && tcs && tcs.length > 0 && !this.selectedTestCase()) {
          this.selectTestCase(tcs[0]);
        }
      },
      error: () => {}
    });
  }

  getCurrentItems(): any[] {
    return this.viewType === 'requirements' ? this.requirements() : this.testCases();
  }

  getSelectedItem(): any {
    return this.viewType === 'requirements' ? this.selectedRequirement() : this.selectedTestCase();
  }

  selectRequirement(req: Requirement) {
    this.selectedRequirement.set(req);
  }

  selectTestCase(tc: TestCase) {
    this.selectedTestCase.set(tc);
  }

  getStatusClass(status: string): string {
    const map: { [key: string]: string } = {
      'Draft': 'status-draft',
      'Approved': 'status-active',
      'Implemented': 'status-progress',
      'Tested': 'status-review',
      'Closed': 'status-completed'
    };
    return map[status] || 'status-default';
  }

  getPriorityClass(priority: string | undefined): string {
    if (!priority) return 'priority-default';
    const p = priority.toUpperCase();
    if (p.includes('P1') || p.includes('CRITICAL')) return 'priority-critical';
    if (p.includes('P2') || p.includes('HIGH')) return 'priority-high';
    if (p.includes('P3') || p.includes('MEDIUM')) return 'priority-medium';
    if (p.includes('P4') || p.includes('LOW')) return 'priority-low';
    return 'priority-default';
  }

  getTypeClass(testType: string | undefined): string {
    if (!testType) return 'status-default';
    const type = testType.toLowerCase();
    if (type === 'positive') return 'status-completed';
    if (type === 'negative') return 'status-draft';
    if (type === 'boundary') return 'status-active';
    if (type === 'performance') return 'status-progress';
    return 'status-default';
  }

  viewRequirementDetail(id: number | undefined) {
    if (id) this.router.navigate(['/requirements', id]);
  }

  viewTestCaseDetail(id: string | undefined) {
    if (id) this.router.navigate(['/test-cases', id]);
  }
}
