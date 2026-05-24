import { Component, OnInit, inject, signal, computed, effect, Input } from '@angular/core';
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
    <div class="split-view-container" [class.embedded]="embedded">
      <!-- Page header is suppressed when this component is embedded inside
           another page (e.g. test-case management's "Browse" layout) so the
           parent's header stays the single source of navigation truth. -->
      <header *ngIf="!embedded" class="management-header">
        <div class="header-left">
          <nav class="breadcrumb">
            <a routerLink="/" class="breadcrumb-link">
              <i class="icon-database"></i>
              Dashboard
            </a>
            <span class="breadcrumb-separator">›</span>
            <a routerLink="/test-cases" class="breadcrumb-link">Test Case Management</a>
            <span class="breadcrumb-separator">›</span>
            <span class="breadcrumb-current">Split View</span>
          </nav>
          <h1 class="page-title">
            <i class="icon-test-cases"></i>
            Test Case Management
          </h1>
        </div>
        <div class="header-right">
          <div class="view-toggle">
            <button class="view-btn" (click)="goToTestCases('grid')" title="Grid View">
              <i class="icon-grid"></i>
            </button>
            <button class="view-btn" (click)="goToTestCases('table')" title="Table View">
              <i class="icon-table"></i>
            </button>
            <button class="view-btn active" title="Browse / Split View (current)" disabled>
              <i class="icon-browse"></i>
            </button>
          </div>
        </div>
      </header>

      <!-- Split Content -->
      <div class="split-content">
        <!-- Left Panel - List View -->
        <div class="list-panel">
          <div class="list-header">
            <div class="list-header-row">
              <h3>{{ viewType === 'requirements' ? 'Requirements' : 'Test Cases' }} ({{ viewType === 'requirements' ? filteredRequirements().length : filteredTestCases().length }})</h3>
              <!-- The type toggle is hidden when the host page already
                   scopes the content (e.g. Test Case Management is exclusively
                   about test cases, so offering Requirements here would be
                   confusing). -->
              <div *ngIf="showTypeToggle" class="type-toggle">
                <button
                  class="type-toggle-btn"
                  [class.active]="viewType === 'requirements'"
                  (click)="viewType = 'requirements'">
                  Requirements
                </button>
                <button
                  class="type-toggle-btn"
                  [class.active]="viewType === 'test-cases'"
                  (click)="viewType = 'test-cases'">
                  Test Cases
                </button>
              </div>
            </div>
            <!-- Inner search box is suppressed when the parent owns the
                 filter UI; otherwise two search inputs would race against
                 each other for the same data. -->
            <input
              *ngIf="showSearch"
              type="text"
              placeholder="Search..."
              [ngModel]="searchTerm()"
              (ngModelChange)="searchTerm.set($event)"
              class="search-input">
          </div>
          
          <div class="list-items" *ngIf="viewType === 'requirements'">
            <div 
              *ngFor="let req of pagedRequirements()" 
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
              *ngFor="let tc of pagedTestCases()" 
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

          <!-- Pagination footer (compact, fits in the narrow list panel) -->
          <div *ngIf="(viewType === 'requirements' ? filteredRequirements().length : filteredTestCases().length) > 0"
               class="list-pagination">
            <div class="pg-info">
              {{ pageStartIndex() }}–{{ pageEndIndex() }} of
              {{ viewType === 'requirements' ? filteredRequirements().length : filteredTestCases().length }}
            </div>
            <div class="pg-controls">
              <select class="pg-size"
                      [value]="pageSize()"
                      (change)="onPageSizeChange($any($event.target).value)"
                      title="Items per page">
                <option [value]="10">10</option>
                <option [value]="20">20</option>
                <option [value]="50">50</option>
                <option [value]="100">100</option>
              </select>
              <button class="pg-btn"
                      (click)="prevPage()"
                      [disabled]="currentPage() === 1"
                      title="Previous page">‹</button>
              <span class="pg-current">{{ currentPage() }} / {{ totalPages() }}</span>
              <button class="pg-btn"
                      (click)="nextPage()"
                      [disabled]="currentPage() >= totalPages()"
                      title="Next page">›</button>
            </div>
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
      /* Use most of the viewport so the list panel has room for ~10 items.
         The 60px reserves space for the app header above the router outlet. */
      height: calc(100vh - 60px);
      min-height: 720px;
      display: flex;
      flex-direction: column;
      padding: 12px 16px;
    }

    /* When embedded inside another page (e.g. test-case management's Browse
       layout) drop the outer padding and our hidden page header's height
       budget — the host page already supplies all the surrounding chrome. */
    .split-view-container.embedded {
      padding: 0;
      min-height: 0;
      height: auto;
      flex: 1 1 auto;
    }

    .management-header {
      background-color: white;
      border: 1px solid #dadce0;
      padding: 10px 16px;
      border-radius: 8px;
      margin-bottom: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
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
      font-size: 20px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    /* --- Mirror of test-case-management header styles so the two pages
       look pixel-identical. If you tweak one, tweak the other. --- */
    .header-right {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .view-toggle {
      display: flex;
      gap: 4px;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 4px;
    }

    .view-btn {
      padding: 8px;
      border: none;
      background: transparent;
      cursor: pointer;
      border-radius: 6px;
      color: #5f6368;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      font-size: 16px;
    }

    .view-btn:hover:not(:disabled) {
      background: #f5f5f5;
      color: #202124;
    }

    .view-btn.active {
      background: #1a73e8;
      color: white;
    }

    .view-btn:disabled {
      cursor: default;
      opacity: 1;
    }

    /* Icons — same glyphs as the management page so the toggle is
       visually identical across the two pages. */
    .icon-test-cases::before { content: "🧪"; }
    .icon-grid::before   { content: "⊞"; font-size: 12px; }
    .icon-table::before  { content: "☰"; font-size: 12px; }
    .icon-browse::before { content: "📍"; font-size: 12px; }

    /* --- Type toggle now lives inside the list-panel header --- */
    .list-header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .type-toggle {
      display: inline-flex;
      border: 1px solid #dadce0;
      border-radius: 16px;
      overflow: hidden;
      background: #f8f9fc;
    }
    .type-toggle-btn {
      padding: 4px 12px;
      border: none;
      background: transparent;
      color: #5f6368;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: background 0.15s, color 0.15s;
    }
    .type-toggle-btn:hover {
      color: #202124;
    }
    .type-toggle-btn.active {
      background: #1a73e8;
      color: white;
    }

    .split-content {
      display: grid;
      grid-template-columns: 450px 1fr;
      gap: 12px;
      flex: 1;
      min-height: 0; /* allow the inner list to scroll instead of pushing the page */
      overflow: hidden;
      border: 1px solid #dadce0;
      border-radius: 8px;
      background: #f5f5f5;
      padding: 12px;
    }

    .list-panel {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-height: 0;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    .list-header {
      padding: 10px 12px;
      border-bottom: 2px solid #dadce0;
      background: white;
      margin: 0;
      flex-shrink: 0;
    }

    .list-header h3 {
      margin: 0 0 8px 0;
      font-size: 14px;
      font-weight: 600;
    }

    .search-input {
      width: 100%;
      padding: 6px 10px;
      border: 1px solid #ddd;
      border-radius: 6px;
      font-size: 13px;
    }

    .list-items {
      padding: 6px 0;
      overflow-y: auto;
      flex: 1;
      min-height: 0;
    }

    /* Compact row layout: each .list-item is ~58-64px tall so the list panel
       comfortably shows 10+ rows at a typical 1080p viewport. */
    .list-item {
      padding: 8px 10px;
      border: 1px solid #dadce0;
      cursor: pointer;
      transition: all 0.2s;
      background: white;
      margin: 0 6px 4px 6px;
      border-radius: 6px;
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
      font-size: 12px;
      margin-bottom: 2px;
      line-height: 1.2;
    }

    .item-title {
      font-size: 13px;
      color: #333;
      margin-bottom: 4px;
      line-height: 1.25;
      font-weight: 500;
      display: -webkit-box;
      -webkit-line-clamp: 1;
      -webkit-box-orient: vertical;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .item-meta {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 2px;
    }

    .badge {
      padding: 2px 6px;
      border-radius: 10px;
      font-size: 10px;
      font-weight: 500;
      line-height: 1.3;
    }

    .detail-panel {
      background: white;
      border: 1px solid #dadce0;
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

    /* Compact pagination footer pinned at the bottom of the list panel.
       flex-shrink: 0 keeps it visible while the .list-items area scrolls. */
    .list-pagination {
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 8px 12px;
      border-top: 1px solid #dadce0;
      background: #fafbfc;
      font-size: 12px;
      color: #5f6368;
    }
    .pg-info {
      white-space: nowrap;
    }
    .pg-controls {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .pg-size {
      padding: 3px 6px;
      border: 1px solid #dadce0;
      border-radius: 4px;
      font-size: 12px;
      background: #fff;
      cursor: pointer;
      margin-right: 4px;
    }
    .pg-btn {
      min-width: 26px;
      height: 26px;
      padding: 0 6px;
      border: 1px solid #dadce0;
      background: #fff;
      color: #202124;
      font-size: 14px;
      line-height: 1;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }
    .pg-btn:hover:not(:disabled) {
      background: #f1f3f4;
      border-color: #c3c8d0;
    }
    .pg-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .pg-current {
      padding: 0 6px;
      font-variant-numeric: tabular-nums;
      color: #202124;
      font-weight: 500;
    }
  `]
})
export class SplitViewComponent implements OnInit {
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);
  private router = inject(Router);

  /** When true, this component is rendered inside another page and should
   * not draw its own page-level header (breadcrumb, title, layout toggle).
   * The parent is responsible for chrome; we just render the split panels. */
  @Input() embedded = false;

  /** Optional override for the initial type-toggle position. The component
   * defaults to 'requirements' for the standalone /split-view entry, but
   * callers (e.g. the Test Case Management page) can switch to 'test-cases'
   * so users land on the panel that matches the page they came from. */
  @Input() set initialViewType(value: 'requirements' | 'test-cases' | undefined) {
    if (value && value !== this._viewType) {
      // Use the setter so the auto-select side effect fires correctly.
      this.viewType = value;
    }
  }

  /** Externally supplied list of test cases. When provided, the component
   * stops fetching its own and renders exactly what the parent passes in
   * (e.g. the already-filtered list from the Test Case Management page).
   * Re-running the auto-select keeps the right-hand detail panel honest
   * when the parent's filters change the visible set. */
  @Input() set externalTestCases(value: TestCase[] | undefined) {
    if (value === undefined) return;
    this._externalTestCasesMode = true;
    this.testCases.set(value);
    if (this._viewType === 'test-cases') {
      this.autoSelectForCurrentType();
    }
  }

  /** Externally supplied list of requirements. Mirrors `externalTestCases`
   * for the Requirements page, which feeds its already-filtered list in
   * so the embedded split panel stays in sync with the page-level filters. */
  @Input() set externalRequirements(value: Requirement[] | undefined) {
    if (value === undefined) return;
    this._externalRequirementsMode = true;
    this.requirements.set(value);
    if (this._viewType === 'requirements') {
      this.autoSelectForCurrentType();
    }
  }

  /** When false, hide the in-panel "Requirements / Test Cases" toggle.
   * Used by the Test Case Management page where showing "Requirements"
   * doesn't make sense. */
  @Input() showTypeToggle = true;

  /** When false, hide the per-panel search input (parent provides its own
   * search/filter UI). */
  @Input() showSearch = true;

  /** True once a caller has piped data in via `externalTestCases`; flips
   * the component into "host owns the data" mode so we don't double-fetch. */
  private _externalTestCasesMode = false;
  private _externalRequirementsMode = false;

  requirements = signal<Requirement[]>([]);
  testCases = signal<TestCase[]>([]);
  selectedRequirement = signal<Requirement | null>(null);
  selectedTestCase = signal<TestCase | null>(null);
  searchTerm = signal('');

  // Backing field for viewType so we can run an auto-select side effect
  // whenever the user flips the toggle. Template still binds via the
  // public `viewType` getter/setter pair.
  private _viewType: 'requirements' | 'test-cases' = 'requirements';
  get viewType(): 'requirements' | 'test-cases' {
    return this._viewType;
  }
  set viewType(value: 'requirements' | 'test-cases') {
    if (this._viewType === value) return;
    this._viewType = value;
    // Reset paging so the freshly-shown list starts at page 1.
    this.currentPage.set(1);
    // Auto-select the first item in the newly active list so the right
    // panel never goes blank just because the user toggled the type.
    this.autoSelectForCurrentType();
  }

  goToPage(page: number) {
    const clamped = Math.max(1, Math.min(this.totalPages(), page));
    this.currentPage.set(clamped);
  }
  prevPage() { this.goToPage(this.currentPage() - 1); }
  nextPage() { this.goToPage(this.currentPage() + 1); }
  onPageSizeChange(size: number | string) {
    const n = typeof size === 'string' ? parseInt(size, 10) : size;
    if (!isNaN(n) && n > 0) {
      this.pageSize.set(n);
      this.currentPage.set(1);
    }
  }

  /** Pick the first item of the currently active list if nothing in that
   * list is selected. Safe to call multiple times — it's a no-op once a
   * row exists. */
  private autoSelectForCurrentType(): void {
    if (this._viewType === 'requirements') {
      const items = this.filteredRequirements();
      if (items.length > 0) {
        // Honor any existing selection only if it's still in the list.
        const current = this.selectedRequirement();
        if (!current || !items.some(r => r.id === current.id)) {
          this.selectRequirement(items[0]);
        }
      } else {
        this.selectedRequirement.set(null);
      }
    } else {
      const items = this.filteredTestCases();
      if (items.length > 0) {
        const current = this.selectedTestCase();
        if (!current || !items.some(tc => tc.test_case_id === current.test_case_id)) {
          this.selectTestCase(items[0]);
        }
      } else {
        this.selectedTestCase.set(null);
      }
    }
  }
  
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

  // Pagination — applies to both lists in the split view. Defaults to 20
  // per page so the narrow list panel doesn't render thousands of rows.
  pageSize = signal(10);
  currentPage = signal(1);
  private currentList = computed(() =>
    this._viewType === 'requirements' ? this.filteredRequirements() : this.filteredTestCases()
  );
  totalPages = computed(() => Math.max(1, Math.ceil(this.currentList().length / this.pageSize())));
  pageStartIndex = computed(() => {
    if (this.currentList().length === 0) return 0;
    return (this.currentPage() - 1) * this.pageSize() + 1;
  });
  pageEndIndex = computed(() =>
    Math.min(this.currentPage() * this.pageSize(), this.currentList().length)
  );
  pagedRequirements = computed(() => {
    const list = this.filteredRequirements();
    const size = this.pageSize();
    const page = Math.min(this.currentPage(), Math.max(1, Math.ceil(list.length / size)));
    const start = (page - 1) * size;
    return list.slice(start, start + size);
  });
  pagedTestCases = computed(() => {
    const list = this.filteredTestCases();
    const size = this.pageSize();
    const page = Math.min(this.currentPage(), Math.max(1, Math.ceil(list.length / size)));
    const start = (page - 1) * size;
    return list.slice(start, start + size);
  });

  constructor() {
    // Reset to page 1 whenever the searched/filtered list shrinks or the
    // user flips between requirements / test-cases so they always land on
    // the first page of the new context.
    effect(() => {
      this.searchTerm();
      // also re-run when the underlying lists change (new data loads)
      this.filteredRequirements();
      this.filteredTestCases();
      this.currentPage.set(1);
    });
    // Clamp current page if the data shrinks below it.
    effect(() => {
      const total = this.totalPages();
      if (this.currentPage() > total) this.currentPage.set(total);
    });
  }

  ngOnInit() {
    if (!this._externalRequirementsMode) {
      this.loadRequirements();
    }
    // Skip our own fetch when a parent is feeding test cases in via the
    // `externalTestCases` input — re-fetching would clobber the parent's
    // already-filtered list with the full, unfiltered set.
    if (!this._externalTestCasesMode) {
      this.loadTestCases();
    }
  }

  /** Navigate back to the test-cases page, restoring the chosen layout
   * via a `view` query param the management page reads on init. */
  goToTestCases(view: 'grid' | 'table'): void {
    this.router.navigate(['/test-cases'], { queryParams: { view } });
  }

  loadRequirements() {
    this.requirementService.getRequirements().subscribe({
      next: (reqs) => {
        this.requirements.set(reqs || []);
        // If the user is currently looking at the requirements list, make
        // sure the right panel has something to render. autoSelect is a
        // no-op when a valid selection is already in place.
        if (this.viewType === 'requirements') {
          this.autoSelectForCurrentType();
        }
      },
      error: () => {}
    });
  }

  loadTestCases() {
    this.testCaseService.getTestCases().subscribe({
      next: (tcs) => {
        this.testCases.set(tcs || []);
        if (this.viewType === 'test-cases') {
          this.autoSelectForCurrentType();
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
