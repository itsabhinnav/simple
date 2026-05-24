import { Component, OnInit, inject, signal, computed, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import {
  TestCaseService,
  TestCase,
  TestCaseCreateRequest,
  TestCaseUpdateRequest,
  TestCaseImportPreview,
  TestCaseImportSheetPreview,
  TestCaseImportResult,
  TestCaseImportDuplicateStrategy
} from '../services/test-case.service';
import { SplitViewComponent } from './split-view.component';

@Component({
  selector: 'app-test-case-management',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule, SplitViewComponent],
  template: `
    <div class="test-case-management-container">
      <!-- Header -->
      <header class="management-header">
        <div class="header-left">
          <nav class="breadcrumb">
            <a routerLink="/" class="breadcrumb-link">
              <i class="icon-database"></i>
              Dashboard
            </a>
            <span class="breadcrumb-separator">›</span>
            <span class="breadcrumb-current">Test Case Management</span>
          </nav>
          <h1 class="page-title">
            <i class="icon-test-cases"></i>
            Test Case Management
          </h1>
        </div>
        <div class="header-right">
          <button
            class="add-btn import-btn"
            (click)="openImportModal()"
            [disabled]="isLoading() || isImporting()"
            title="Import test cases from one or more spreadsheets (.xlsx, .xlsm, .csv)">
            <i class="icon-upload"></i>
            Import Test Cases
          </button>
          <button 
            class="add-btn" 
            routerLink="/test-cases/create"
            [disabled]="isLoading()">
            <i class="icon-plus"></i>
            Add New Test Case
          </button>
          <div class="view-toggle">
            <button class="view-btn" [class.active]="currentView() === 'grid'" (click)="currentView.set('grid')" title="Grid View">
              <i class="icon-grid"></i>
            </button>
            <button class="view-btn" [class.active]="currentView() === 'table'" (click)="currentView.set('table')" title="Table View">
              <i class="icon-table"></i>
            </button>
            <button class="view-btn" [class.active]="currentView() === 'browse'" (click)="currentView.set('browse')" title="Browse View">
              <i class="icon-browse"></i>
            </button>
          </div>
        </div>
      </header>

      <!-- Loading State -->
      <div *ngIf="isLoading()" class="loading-container">
        <div class="spinner"></div>
        <p>Loading test cases...</p>
      </div>

      <!-- Error State -->
      <div *ngIf="error()" class="error-container">
        <i class="icon-error"></i>
        <p>{{ error() }}</p>
        <button (click)="loadTestCases()" class="retry-btn">Retry</button>
      </div>

      <!-- Filters -->
      <div class="filters-section">
        <div class="filter-tabs">
          <input 
            type="text" 
            placeholder="Search test cases..." 
            class="global-search-input"
            [ngModel]="searchTerm()"
            (ngModelChange)="searchTerm.set($event)">
          <div class="filter-dropdown" (click)="$event.stopPropagation()">
            <button class="filter-btn-blue" [class.active]="showFeatureFilter()" (click)="toggleFilter('feature', $event)">
              feature ▼
              <span class="filter-count" *ngIf="selectedFeatures().length > 0">+{{ selectedFeatures().length }}</span>
            </button>
          </div>
          <div class="filter-dropdown" (click)="$event.stopPropagation()">
            <button class="filter-btn-blue" [class.active]="showScreenIdFilter()" (click)="toggleFilter('screenId', $event)">
              Screen ID ▼
              <span class="filter-count" *ngIf="selectedScreenIds().length > 0">+{{ selectedScreenIds().length }}</span>
            </button>
          </div>
          <div class="filter-dropdown" (click)="$event.stopPropagation()">
            <button class="filter-btn-blue" [class.active]="showTypeFilter()" (click)="toggleFilter('type', $event)">
              test type ▼
              <span class="filter-count" *ngIf="selectedTypes().length > 0">+{{ selectedTypes().length }}</span>
            </button>
          </div>
          <div class="filter-dropdown" (click)="$event.stopPropagation()">
            <button class="filter-btn-blue" [class.active]="showTestSuiteTypeFilter()" (click)="toggleFilter('testsuiteType', $event)">
              TestSuite Type ▼
              <span class="filter-count" *ngIf="selectedTestSuiteTypes().length > 0">+{{ selectedTestSuiteTypes().length }}</span>
            </button>
          </div>
          <div class="filter-dropdown" (click)="$event.stopPropagation()">
            <button class="filter-btn-blue" [class.active]="showRequirementTypeFilter()" (click)="toggleFilter('requirementType', $event)">
              Requirement Type ▼
              <span class="filter-count" *ngIf="selectedRequirementTypes().length > 0">+{{ selectedRequirementTypes().length }}</span>
            </button>
          </div>
          <button class="filter-btn-more" (click)="toggleMoreFilters()">More filters ▼</button>
          <button class="clear-filters-btn" (click)="clearAllFilters()">Clear filters</button>
        </div>

        <!-- Type Filter Dropdown -->
        <div class="filter-panel" *ngIf="showTypeFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header">
            <span>Type = (equals)</span>
          </div>
          <input type="text" placeholder="Search Type" class="filter-search" [(ngModel)]="typeSearchTerm">
          <div class="filter-options">
            <label *ngFor="let type of getTypeOptions()" class="filter-option">
              <input type="checkbox" [checked]="isTypeSelected(type)" (change)="toggleType(type)">
              <span class="filter-label">{{ type }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearTypes()">Clear selection</button>
            <span class="filter-count-info">{{ getSelectedTypesCount() }} of {{ getTypeOptions().length }}</span>
          </div>
        </div>

        <!-- Priority Filter Dropdown -->
        <div class="filter-panel" *ngIf="showPriorityFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header">
            <span>Priority = (equals)</span>
          </div>
          <input type="text" placeholder="Search Priority" class="filter-search" [(ngModel)]="prioritySearchTerm">
          <div class="filter-options">
            <label *ngFor="let priority of getPriorityOptions()" class="filter-option">
              <input type="checkbox" [checked]="isPrioritySelected(priority)" (change)="togglePriority(priority)">
              <span class="filter-label">{{ priority }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearPriorities()">Clear selection</button>
            <span class="filter-count-info">{{ getSelectedPrioritiesCount() }} of {{ getPriorityOptions().length }}</span>
          </div>
        </div>

        <!-- Feature Filter Dropdown -->
        <div class="filter-panel" *ngIf="showFeatureFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header">
            <span>Feature = (equals)</span>
          </div>
          <input type="text" placeholder="Search Feature" class="filter-search" [(ngModel)]="featureSearchTerm">
          <div class="filter-options">
            <label *ngFor="let feature of getFilteredFeatures()" class="filter-option">
              <input type="checkbox" [checked]="isFeatureSelected(feature)" (change)="toggleFeature(feature)">
              <span class="filter-label">{{ feature }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearFeatures()">Clear selection</button>
            <span class="filter-count-info">{{ getSelectedFeaturesCount() }} of {{ getFilteredFeatures().length }}</span>
          </div>
        </div>

        <!-- Screen ID Filter Dropdown -->
        <div class="filter-panel" *ngIf="showScreenIdFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header">
            <span>Screen ID = (equals)</span>
          </div>
          <input type="text" placeholder="Search Screen ID" class="filter-search" [(ngModel)]="screenIdSearchTerm">
          <div class="filter-options">
            <label *ngFor="let screenId of getFilteredScreenIds()" class="filter-option">
              <input type="checkbox" [checked]="isScreenIdSelected(screenId)" (change)="toggleScreenId(screenId)">
              <span class="filter-label">{{ screenId }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearScreenIds()">Clear selection</button>
            <span class="filter-count-info">{{ getSelectedScreenIdsCount() }} of {{ getFilteredScreenIds().length }}</span>
          </div>
        </div>

        <!-- TestSuite Type Filter Dropdown -->
        <div class="filter-panel" *ngIf="showTestSuiteTypeFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header">
            <span>TestSuite Type = (equals)</span>
          </div>
          <input type="text" placeholder="Search TestSuite Type" class="filter-search" [(ngModel)]="testSuiteTypeSearchTerm">
          <div class="filter-options">
            <label *ngFor="let type of getFilteredTestSuiteTypes()" class="filter-option">
              <input type="checkbox" [checked]="isTestSuiteTypeSelected(type)" (change)="toggleTestSuiteType(type)">
              <span class="filter-label">{{ type }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearTestSuiteTypes()">Clear selection</button>
            <span class="filter-count-info">{{ getSelectedTestSuiteTypesCount() }} of {{ getFilteredTestSuiteTypes().length }}</span>
          </div>
        </div>

        <!-- Requirement Type Filter Dropdown -->
        <div class="filter-panel" *ngIf="showRequirementTypeFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header">
            <span>Requirement Type = (equals)</span>
          </div>
          <input type="text" placeholder="Search Requirement Type" class="filter-search" [(ngModel)]="requirementTypeSearchTerm">
          <div class="filter-options">
            <label *ngFor="let type of getFilteredRequirementTypes()" class="filter-option">
              <input type="checkbox" [checked]="isRequirementTypeSelected(type)" (change)="toggleRequirementType(type)">
              <span class="filter-label">{{ type }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearRequirementTypes()">Clear selection</button>
            <span class="filter-count-info">{{ getSelectedRequirementTypesCount() }} of {{ getFilteredRequirementTypes().length }}</span>
          </div>
        </div>
      </div>

      <!-- Test Cases Board (JIRA-like) -->
      <div *ngIf="!isLoading() && !error()" class="board-container">
        <div class="board-header">
          <h3>Test Cases ({{ filteredTestCases().length }})</h3>
        </div>
        
        <!-- Empty State -->
        <div *ngIf="filteredTestCases().length === 0" class="empty-state">
          <i class="icon-empty"></i>
          <h3>No Test Cases Found</h3>
          <p *ngIf="searchTerm || selectedTypes().length > 0 || selectedPriorities().length > 0 || selectedFeatures().length > 0">
            No test cases match your filter criteria.
          </p>
          <p *ngIf="!searchTerm && selectedTypes().length === 0 && selectedPriorities().length === 0 && selectedFeatures().length === 0">
            No test cases available. Create your first test case!
          </p>
        </div>

        <!-- Browse / Split View — embedded so the management page header
             stays put; only this content area changes when the user toggles
             between Grid / Table / Browse. -->
        <div *ngIf="currentView() === 'browse'" class="browse-view-container">
          <!-- Feed the parent's already-filtered test cases in so the
               panel respects the search box, type / priority / feature
               filters from the page header above. The type toggle and
               inner search are hidden — this page is exclusively about
               test cases and the parent already provides search UI. -->
          <app-split-view
            [embedded]="true"
            initialViewType="test-cases"
            [externalTestCases]="filteredTestCases()"
            [showTypeToggle]="false"
            [showSearch]="false">
          </app-split-view>
        </div>

        <!-- Table View -->
        <div *ngIf="filteredTestCases().length > 0 && currentView() === 'table'" class="table-view-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Test Case ID</th>
                <th>Title</th>
                <th>Vehicle Model</th>
                <th>Severity</th>
                <th>Type</th>
                <th>Priority</th>
                <th>Feature</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let tc of filteredTestCases()" (click)="navigateToDetail(tc.test_case_id)" style="cursor: pointer;">
                <td><strong>{{ tc.test_case_id }}</strong></td>
                <td>{{ tc.title || tc.test_objective || '-' }}</td>
                <td>{{ tc.vehicle_model || '-' }}</td>
                <td>
                  <span class="severity-badge" [class]="getSeverityClass(tc.severity)">
                    {{ tc.severity || '-' }}
                  </span>
                </td>
                <td><span class="type-badge">{{ tc.test_type || '-' }}</span></td>
                <td><span class="priority-badge" [class]="getPriorityClass(tc.priority)">{{ tc.priority || 'P3' }}</span></td>
                <td>{{ tc.feature || '-' }}</td>
                <td (click)="$event.stopPropagation()">
                  <div class="actions">
                    <button class="btn-edit" (click)="openEditModal(tc)" title="Edit" aria-label="Edit">
                      <i class="icon-edit"></i>
                    </button>
                    <button class="btn-delete" (click)="confirmDelete(tc)" title="Delete" aria-label="Delete">
                      <i class="icon-delete"></i>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Grid View -->
        <div *ngIf="filteredTestCases().length > 0 && currentView() === 'grid'" class="requirements-grid">
          <div *ngFor="let tc of filteredTestCases()" class="requirement-card" (click)="navigateToDetail(tc.test_case_id)">
            <div class="card-header">
              <span class="req-id">{{ tc.test_case_id }}</span>
              <span class="priority-badge" [class]="getPriorityClass(tc.priority)">
                {{ tc.priority || 'P3' }}
              </span>
            </div>
            <h3 class="card-title">{{ tc.title || tc.test_objective || 'Test Case' }}</h3>
            <p class="card-description" *ngIf="tc.vehicle_model">🚗 {{ tc.vehicle_model }}<span *ngIf="tc.severity"> · {{ tc.severity }}</span></p>
            <p class="card-description" *ngIf="tc.feature">Feature: {{ tc.feature }}</p>
            <p class="card-description" *ngIf="tc.description || tc.preconditions">{{ tc.description || tc.preconditions }}</p>
            
            <div class="card-footer">
              <span class="status-badge" [class]="getTypeClass(tc.test_type)">
                {{ tc.test_type || 'N/A' }}
              </span>
              <span class="assignee" *ngIf="tc.feature">👤 {{ tc.feature }}</span>
            </div>
            <div class="card-actions" (click)="$event.stopPropagation()">
              <button class="btn-edit" (click)="openEditModal(tc)" title="Edit">
                <i class="icon-edit"></i>
              </button>
              <button class="btn-delete" (click)="confirmDelete(tc)" title="Delete">
                <i class="icon-delete"></i>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Excel Import Modal -->
      <div *ngIf="showImportModal()" class="modal-overlay" (click)="closeImportModal()">
        <div class="modal-content import-modal" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <h2>
              Import Test Cases from Excel
              <span *ngIf="importStep() === 'mapping'" class="modal-subtitle"> · Review column mapping</span>
              <span *ngIf="importStep() === 'result'" class="modal-subtitle"> · Result</span>
            </h2>
            <button class="close-btn" (click)="closeImportModal()">
              <i class="icon-close"></i>
            </button>
          </div>

          <div class="modal-body">
            <!-- STEP 1: file pick + format help -->
            <div *ngIf="importStep() === 'select'">
              <p class="import-hint">
                Upload one or more <strong>.xlsx</strong>, <strong>.xlsm</strong>, or
                <strong>.csv</strong> files. We'll inspect the headers and auto-match them to
                the test-case fields. You'll get to review the mapping before anything is
                written.
              </p>
              <div class="import-dropzone">
                <input
                  type="file"
                  multiple
                  accept=".xlsx,.xlsm,.csv"
                  (change)="onImportFilesSelected($event)"
                  #importInput>
                <p *ngIf="importFiles().length === 0" class="dropzone-hint">
                  Click to choose spreadsheet files (Excel or CSV, 10k+ rows per file is fine).
                </p>
                <ul *ngIf="importFiles().length > 0" class="import-file-list">
                  <li *ngFor="let f of importFiles()">
                    <i class="icon-file"></i> {{ f.name }} <span class="file-size">({{ formatBytes(f.size) }})</span>
                  </li>
                </ul>
              </div>
              <label class="import-toggle">
                <input
                  type="checkbox"
                  [checked]="importReplaceDuplicates()"
                  (change)="importReplaceDuplicates.set($any($event.target).checked)">
                Replace existing rows with the same ID
                <span class="import-toggle-hint">
                  · off = skip duplicates (default), on = overwrite them in place
                </span>
              </label>
              <p class="import-error" *ngIf="importError()">{{ importError() }}</p>
              <div class="form-actions">
                <button type="button" class="btn-cancel" (click)="closeImportModal()">Cancel</button>
                <button
                  type="button"
                  class="btn-submit"
                  [disabled]="importFiles().length === 0 || isPreviewing()"
                  (click)="previewSelectedFile()">
                  <span *ngIf="isPreviewing()" class="spinner-small"></span>
                  {{ isPreviewing() ? 'Reading workbook…' : 'Preview & Map Columns' }}
                </button>
                <button
                  type="button"
                  class="btn-submit btn-secondary-import"
                  [disabled]="importFiles().length === 0 || isImporting()"
                  (click)="importNow()"
                  title="Skip the mapping step and rely on auto-detection only.">
                  <span *ngIf="isImporting()" class="spinner-small"></span>
                  {{ isImporting() ? 'Importing…' : 'Import (auto-detect)' }}
                </button>
              </div>
            </div>

            <!-- STEP 2: mapping editor -->
            <div *ngIf="importStep() === 'mapping' && importPreview() as preview">
              <p class="import-hint">
                File: <strong>{{ preview.file }}</strong>. Confirm or fix the mapping for each
                column, then click Import.
              </p>
              <div *ngFor="let sheet of preview.sheets" class="import-sheet-block">
                <h4 class="import-sheet-title">
                  Sheet "{{ sheet.sheet }}"
                  <span class="import-sheet-meta">
                    {{ sheet.row_count_estimate }} row(s), {{ sheet.raw_headers.length }} column(s)
                  </span>
                </h4>
                <table class="mapping-table">
                  <thead>
                    <tr>
                      <th>Column in spreadsheet</th>
                      <th>Maps to test-case field</th>
                      <th>Sample value</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr *ngFor="let header of sheet.raw_headers; let i = index">
                      <td><code>{{ header }}</code></td>
                      <td>
                        <select
                          [value]="getMappingValue(header)"
                          (change)="setMappingValue(header, $any($event.target).value)">
                          <option value="">— Ignore this column —</option>
                          <option *ngFor="let f of importFields()" [value]="f">{{ f }}</option>
                        </select>
                      </td>
                      <td class="sample-cell">{{ sampleValueFor(sheet, i) || '' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <label class="import-toggle">
                <input
                  type="checkbox"
                  [checked]="importReplaceDuplicates()"
                  (change)="importReplaceDuplicates.set($any($event.target).checked)">
                Replace existing rows with the same ID
                <span class="import-toggle-hint">
                  · off = skip duplicates (default), on = overwrite them in place
                </span>
              </label>
              <p class="import-error" *ngIf="importError()">{{ importError() }}</p>
              <div class="form-actions">
                <button type="button" class="btn-cancel" (click)="backToSelect()">Back</button>
                <button
                  type="button"
                  class="btn-submit"
                  [disabled]="isImporting()"
                  (click)="importWithMapping()">
                  <span *ngIf="isImporting()" class="spinner-small"></span>
                  {{ isImporting() ? 'Importing…' : 'Import with this mapping' }}
                </button>
              </div>
            </div>

            <!-- STEP 3: result summary -->
            <div *ngIf="importStep() === 'result' && importResult() as result">
              <div class="import-summary">
                <span class="summary-pill summary-created">
                  Created: <strong>{{ result.totals.created }}</strong>
                </span>
                <span class="summary-pill summary-updated">
                  Updated: <strong>{{ result.totals.updated || 0 }}</strong>
                </span>
                <span class="summary-pill summary-skipped">
                  Skipped: <strong>{{ result.totals.skipped }}</strong>
                </span>
                <span class="summary-pill summary-failed">
                  Failed: <strong>{{ result.totals.failed }}</strong>
                </span>
              </div>
              <div *ngFor="let file of result.files" class="import-file-result">
                <h4>{{ file.file }}</h4>
                <p>
                  Created {{ file.created }}, updated {{ file.updated || 0 }},
                  skipped {{ file.skipped }}, failed {{ file.failed }}.
                </p>
                <details *ngIf="file.errors.length > 0">
                  <summary>{{ file.errors.length }} error(s) — first 20 shown</summary>
                  <ul class="error-list">
                    <li *ngFor="let err of file.errors.slice(0, 20)">
                      <ng-container *ngIf="err.sheet">[{{ err.sheet }}] </ng-container>
                      <ng-container *ngIf="err.row">Row {{ err.row }}: </ng-container>
                      <ng-container *ngIf="err.id">{{ err.id }} — </ng-container>
                      {{ err.error }}
                    </li>
                  </ul>
                </details>
              </div>
              <div class="form-actions">
                <button type="button" class="btn-cancel" (click)="backToSelect()">Import more</button>
                <button type="button" class="btn-submit" (click)="closeImportModal()">Done</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Delete Confirmation Modal -->
      <div *ngIf="showDeleteModalSignal()" class="modal-overlay" (click)="cancelDelete()">
        <div class="modal-content delete-modal" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <h2>Confirm Delete</h2>
            <button class="close-btn" (click)="cancelDelete()">
              <i class="icon-close"></i>
            </button>
          </div>
          <div class="modal-body">
            <p>Are you sure you want to delete test case <strong>{{ testCaseToDelete()?.test_case_id }}</strong>?</p>
            <p class="warning-text">This action cannot be undone.</p>
            <div class="form-actions">
              <button 
                type="button" 
                class="btn-cancel" 
                (click)="cancelDelete()">
                Cancel
              </button>
              <button 
                type="button" 
                class="btn-delete-confirm"
                (click)="deleteTestCase()"
                [disabled]="isDeleting()">
                <span *ngIf="isDeleting()" class="spinner-small"></span>
                Delete Test Case
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .test-case-management-container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 20px;
    }

    .management-header {
      background-color: white;
      border: 1px solid #dadce0;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 24px;
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

    .view-btn:hover {
      background: #f5f5f5;
      color: #202124;
    }

    .view-btn.active {
      background: #1a73e8;
      color: white;
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
      display: flex;
      align-items: center;
      gap: 5px;
      transition: color 0.2s;
      font-size: 14px;
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
      font-size: 14px;
    }

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .add-btn {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px;
      background: #1a73e8;
      color: white;
      border: none;
      border-radius: 24px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
      text-decoration: none;
    }

    .add-btn:hover:not(:disabled) {
      background: #1557b0;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    }

    .add-btn:disabled {
      background: #dadce0;
      cursor: not-allowed;
    }

    .loading-container, .error-container {
      text-align: center;
      padding: 60px 20px;
    }

    .spinner {
      width: 40px;
      height: 40px;
      border: 4px solid #f3f3f3;
      border-top: 4px solid #1a73e8;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }

    .spinner-small {
      width: 16px;
      height: 16px;
      border: 2px solid transparent;
      border-top: 2px solid currentColor;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      display: inline-block;
      margin-right: 8px;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .table-container {
      background: white;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    }

    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .table-header h3 {
      margin: 0;
      color: #333;
    }

    .search-box {
      position: relative;
    }

    .search-input {
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 6px;
      width: 250px;
      font-size: 14px;
    }

    .search-input:focus {
      outline: none;
      border-color: #4caf50;
      box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
    }

    .table-wrapper {
      overflow-x: auto;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
    }

    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }

    .data-table th {
      background: #f5f5f5;
      color: #333;
      font-weight: 600;
      padding: 12px 16px;
      text-align: left;
      border-bottom: 2px solid #e0e0e0;
      white-space: nowrap;
    }

    .data-table td {
      padding: 12px 16px;
      border-bottom: 1px solid #e0e0e0;
      vertical-align: top;
    }

    .data-table tbody tr:hover {
      background: #f9f9f9;
    }

    .data-table tbody tr:last-child td {
      border-bottom: none;
    }

    .priority-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }

    .priority-p1 { background: #ffebee; color: #c62828; }
    .priority-p2 { background: #fff3e0; color: #ef6c00; }
    .priority-p3 { background: #e8f5e8; color: #2e7d32; }
    .priority-low { background: #e8f5e8; color: #2e7d32; }
    .priority-medium { background: #fff3e0; color: #ef6c00; }
    .priority-high { background: #ffebee; color: #c62828; }
    .priority-default { background: #f5f5f5; color: #757575; }

    .complexity-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      text-transform: capitalize;
    }

    .complexity-badge.high { background: #ffebee; color: #c62828; }
    .complexity-badge.medium { background: #fff3e0; color: #ef6c00; }
    .complexity-badge.low { background: #e8f5e8; color: #2e7d32; }

    .status-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }

    .status-badge.has-requirements { background: #e8f5e8; color: #2e7d32; }
    .status-badge.no-requirements { background: #fafafa; color: #757575; }
    .status-draft { background: #f5f5f5; color: #757575; }
    .status-active { background: #e3f2fd; color: #1976d2; }
    .status-progress { background: #fff3e0; color: #f57c00; }
    .status-review { background: #f3e5f5; color: #7b1fa2; }
    .status-completed { background: #e8f5e8; color: #2e7d32; }
    .status-default { background: #fafafa; color: #757575; }

    .actions {
      display: flex;
      gap: 8px;
    }

    .btn-edit, .btn-delete {
      padding: 6px 8px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      line-height: 1;
    }

    .btn-edit {
      background: #e3f2fd;
      color: #1976d2;
    }

    .btn-edit:hover {
      background: #bbdefb;
    }

    .btn-delete {
      background: #ffebee;
      color: #c62828;
    }

    .btn-delete:hover {
      background: #ffcdd2;
    }

    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: #666;
    }

    .assignee {
      font-size: 12px;
      color: #666;
    }

    .requirements-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }

    .requirement-card {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 16px;
      transition: all 0.2s;
      cursor: pointer;
    }

    .requirement-card:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .req-id {
      font-weight: 600;
      color: #1a73e8;
      font-size: 13px;
    }

    .card-title {
      margin: 8px 0;
      font-size: 16px;
      font-weight: 600;
      color: #333;
    }

    .card-description {
      font-size: 14px;
      color: #666;
      margin: 8px 0;
      line-height: 1.5;
    }

    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid #f0f0f0;
    }

    .card-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid #f0f0f0;
    }

    .filters-section {
      background: white;
      padding: 16px;
      border: 1px solid #dadce0;
      border-radius: 8px;
      margin-bottom: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .search-filter {
      width: 100%;
    }

    .select-filters {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
    }

    .filter-select {
      padding: 10px;
      border: 1px solid #dadce0;
      border-radius: 6px;
      font-size: 14px;
      background: white;
    }

    .board-container {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 24px;
    }

    .board-header h3 {
      margin: 0 0 16px 0;
      color: #333;
    }

    /* Filter Panel Styles */
    .filter-tabs {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;
      position: relative;
      z-index: 1;
    }

    .global-search-input {
      flex: 1;
      min-width: 200px;
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-size: 14px;
    }

    .filter-dropdown {
      position: relative;
      z-index: 10;
    }

    .filter-btn-blue {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border: none;
      border-radius: 4px;
      background: #1a73e8;
      color: white;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
    }

    .filter-btn-blue:hover {
      background: #1557b0;
    }

    .filter-btn-blue.active {
      background: #1557b0;
    }

    .filter-btn-more {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border: 1px solid #ddd;
      border-radius: 4px;
      background: white;
      color: #333;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
    }

    .filter-btn-more:hover {
      background: #f5f5f5;
    }

    .filter-count {
      background: #fff;
      color: #1a73e8;
      border-radius: 12px;
      padding: 2px 6px;
      font-size: 11px;
      font-weight: 600;
    }

    .clear-filters-btn {
      padding: 8px 16px;
      background: none;
      border: 1px solid #ddd;
      border-radius: 4px;
      color: #333;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }

    .clear-filters-btn:hover {
      background: #f5f5f5;
    }

    .filter-panel {
      position: fixed;
      background: white;
      border: 1px solid #ddd;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      min-width: 300px;
      max-width: 400px;
      max-height: 500px;
      overflow-y: auto;
      z-index: 1050;
    }

    .filter-panel-header {
      padding: 12px;
      border-bottom: 1px solid #eee;
      font-size: 13px;
      font-weight: 500;
      color: #666;
    }

    .filter-search {
      width: 100%;
      padding: 8px 12px;
      border: none;
      border-bottom: 1px solid #eee;
      font-size: 14px;
    }

    .filter-search:focus {
      outline: none;
    }

    .filter-options {
      max-height: 300px;
      overflow-y: auto;
      padding: 8px 0;
    }

    .filter-option {
      display: flex;
      align-items: center;
      padding: 8px 12px;
      cursor: pointer;
      transition: background 0.2s;
    }

    .filter-option:hover {
      background: #f5f5f5;
    }

    .filter-option input[type="checkbox"] {
      margin-right: 8px;
      cursor: pointer;
    }

    .filter-label {
      font-size: 14px;
      color: #333;
    }

    .filter-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      border-top: 1px solid #eee;
      font-size: 12px;
    }

    .filter-clear {
      background: none;
      border: none;
      color: #1a73e8;
      cursor: pointer;
      font-size: 12px;
      transition: color 0.2s;
    }

    .filter-clear:hover {
      color: #1557b0;
    }

    .filter-count-info {
      color: #666;
    }

    .retry-btn {
      background: #1a73e8;
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 24px;
      cursor: pointer;
      font-weight: 500;
      margin-top: 15px;
      transition: all 0.2s;
    }

    .retry-btn:hover {
      background: #1557b0;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    }

    /* Modal Styles */
    .modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }

    .modal-content {
      background: white;
      border-radius: 12px;
      width: 90%;
      max-width: 600px;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    }

    .delete-modal {
      max-width: 400px;
    }

    .modal-header {
      padding: 20px;
      border-bottom: 1px solid #e0e0e0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .modal-header h2 {
      margin: 0;
      color: #333;
    }

    .close-btn {
      background: none;
      border: none;
      font-size: 20px;
      cursor: pointer;
      color: #666;
      padding: 0;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .close-btn:hover {
      color: #333;
    }

    .modal-body {
      padding: 20px;
    }

    .form-group {
      margin-bottom: 20px;
    }

    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 15px;
    }

    .form-group label {
      display: block;
      margin-bottom: 5px;
      font-weight: 500;
      color: #333;
    }

    .form-input, .form-select, .form-textarea {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #ddd;
      border-radius: 6px;
      font-size: 14px;
      transition: border-color 0.2s;
      font-family: inherit;
    }

    .form-input:focus, .form-select:focus, .form-textarea:focus {
      outline: none;
      border-color: #4caf50;
      box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
    }

    .form-input.error {
      border-color: #c62828;
    }

    .form-textarea {
      resize: vertical;
      min-height: 80px;
    }

    .error-message {
      color: #c62828;
      font-size: 12px;
      margin-top: 5px;
    }

    .form-actions {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid #e0e0e0;
    }

    .btn-cancel, .btn-submit, .btn-delete-confirm {
      padding: 10px 20px;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.2s;
    }

    .btn-cancel {
      background: #f5f5f5;
      color: #666;
    }

    .btn-cancel:hover {
      background: #e0e0e0;
    }

    .btn-submit {
      background: #1a73e8;
      color: white;
    }

    .btn-submit:hover:not(:disabled) {
      background: #1557b0;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    }

    .btn-submit:disabled {
      background: #bdbdbd;
      cursor: not-allowed;
    }

    .btn-delete-confirm {
      background: #c62828;
      color: white;
    }

    .btn-delete-confirm:hover:not(:disabled) {
      background: #b71c1c;
    }

    .btn-delete-confirm:disabled {
      background: #bdbdbd;
      cursor: not-allowed;
    }

    .warning-text {
      color: #c62828;
      font-weight: 500;
      margin-top: 10px;
    }

    /* Icons */
    .icon-test-cases::before { content: "🧪"; }
    .icon-plus::before { content: "➕"; }
    .icon-error::before { content: "❌"; }
    .icon-empty::before { content: "📭"; }
    .icon-edit::before { content: "✏️"; }
    .icon-delete::before { content: "🗑️"; }
    .icon-close::before { content: "✕"; }
    .icon-grid::before { content: "⊞"; font-size: 12px; }
    .icon-table::before { content: "☰"; font-size: 12px; }
    .icon-browse::before { content: "📍"; font-size: 12px; }
    .icon-database::before { content: "📊"; }

    /* Table View Styles */
    .table-view-container {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      overflow: hidden;
    }

    /* Browse layout — host for the embedded SplitViewComponent. Give it a
       fixed-ish viewport height so the inner panels can scroll independently
       without pushing the page header off-screen. */
    .browse-view-container {
      display: flex;
      flex-direction: column;
      min-height: 0;
      /* Reserve room for the app shell + management header + filter row. */
      height: calc(100vh - 220px);
      min-height: 600px;
    }

    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }

    .data-table th {
      background: #f5f5f5;
      color: #333;
      font-weight: 600;
      padding: 12px 16px;
      text-align: left;
      border-bottom: 2px solid #e0e0e0;
    }

    .data-table td {
      padding: 12px 16px;
      border-bottom: 1px solid #e0e0e0;
    }

    .data-table tbody tr:hover {
      background: #f9f9f9;
    }

    .data-table tbody tr:last-child td {
      border-bottom: none;
    }

    .type-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      display: inline-block;
    }

    /* Severity badges — used in table view */
    .severity-badge {
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 600;
      display: inline-block;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      color: #fff;
      background: #9aa0a6;
    }
    .severity-blocker  { background: #b00020; }
    .severity-critical { background: #d93025; }
    .severity-major    { background: #e8710a; }
    .severity-minor    { background: #1a73e8; }
    .severity-trivial  { background: #5f6368; }
    .severity-default  { background: #9aa0a6; }

    /* Import button accent */
    .import-btn {
      background: #1a73e8;
    }
    .import-btn:hover { background: #1765c1; }

    /* Excel import modal */
    .import-modal {
      max-width: 880px;
      width: 95%;
    }
    .modal-subtitle {
      font-weight: 400;
      color: #5f6368;
      font-size: 14px;
    }
    .import-hint {
      color: #3c4043;
      margin: 0 0 16px 0;
      line-height: 1.5;
    }
    .import-dropzone {
      border: 2px dashed #c3c8d0;
      border-radius: 8px;
      padding: 24px;
      text-align: center;
      background: #f8f9fc;
      margin-bottom: 16px;
      cursor: pointer;
    }
    .import-dropzone input[type="file"] {
      display: block;
      margin: 0 auto;
    }
    .dropzone-hint {
      margin: 12px 0 0 0;
      color: #5f6368;
      font-size: 13px;
    }
    .import-file-list {
      list-style: none;
      padding: 12px 0 0 0;
      margin: 12px 0 0 0;
      text-align: left;
    }
    .import-file-list li {
      padding: 6px 0;
      border-bottom: 1px solid #ececec;
      color: #202124;
    }
    .import-file-list li:last-child { border-bottom: none; }
    .file-size { color: #5f6368; font-size: 12px; margin-left: 6px; }

    .import-sheet-block {
      border: 1px solid #dadce0;
      border-radius: 6px;
      padding: 12px 14px;
      margin-bottom: 16px;
      background: #fff;
    }
    .import-sheet-title {
      margin: 0 0 10px 0;
      font-size: 14px;
      color: #202124;
    }
    .import-sheet-meta {
      color: #5f6368;
      font-weight: 400;
      font-size: 12px;
      margin-left: 8px;
    }
    .mapping-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    .mapping-table th,
    .mapping-table td {
      padding: 6px 8px;
      border-bottom: 1px solid #f1f3f4;
      text-align: left;
      vertical-align: top;
    }
    .mapping-table th {
      color: #5f6368;
      font-weight: 600;
    }
    .mapping-table code {
      background: #f1f3f4;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Menlo', 'Consolas', monospace;
      font-size: 12px;
    }
    .mapping-table select {
      width: 100%;
      padding: 4px 6px;
      border: 1px solid #dadce0;
      border-radius: 4px;
      background: #fff;
    }
    .sample-cell {
      color: #5f6368;
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .import-summary {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }
    .summary-pill {
      padding: 6px 12px;
      border-radius: 14px;
      font-size: 13px;
      background: #f1f3f4;
      color: #202124;
    }
    .summary-created { background: #e6f4ea; color: #137333; }
    .summary-updated { background: #e8f0fe; color: #1967d2; }
    .summary-skipped { background: #fef7e0; color: #b06000; }
    .summary-failed  { background: #fce8e6; color: #b00020; }

    /* Duplicate-strategy toggle */
    .import-toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      margin: 8px 0 12px 0;
      background: #f8f9fc;
      border: 1px solid #dadce0;
      border-radius: 6px;
      font-size: 13px;
      color: #202124;
      cursor: pointer;
    }
    .import-toggle input[type="checkbox"] {
      width: 16px;
      height: 16px;
      cursor: pointer;
    }
    .import-toggle-hint {
      color: #5f6368;
      font-weight: 400;
      font-size: 12px;
    }

    .import-file-result {
      border: 1px solid #f1f3f4;
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 10px;
    }
    .import-file-result h4 {
      margin: 0 0 6px 0;
      font-size: 14px;
    }
    .error-list {
      margin: 6px 0 0 20px;
      padding: 0;
      font-size: 12px;
      color: #b00020;
    }
    .error-list li {
      margin: 2px 0;
    }

    .import-error {
      color: #b00020;
      background: #fce8e6;
      padding: 8px 12px;
      border-radius: 6px;
      margin: 8px 0;
      font-size: 13px;
    }

    .btn-secondary-import {
      background: #f1f3f4;
      color: #1a73e8;
      border: 1px solid #1a73e8;
    }
    .btn-secondary-import:hover {
      background: #e8f0fe;
    }
  `]
})
export class TestCaseManagementComponent implements OnInit {
  private testCaseService = inject(TestCaseService);
  private formBuilder = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private readonly isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  // Signals for reactive state management
  testCases = signal<TestCase[]>([]);
  isLoading = signal(false);
  error = signal<string | null>(null);
  showModal = signal(false);
  currentView = signal<'grid' | 'table' | 'browse'>('table');
  
  // Computed signal for filtered test cases
  filteredTestCases = computed(() => {
    let filtered = this.testCases();
    
    // Text search
    if (this.searchTerm().trim()) {
      const term = this.searchTerm().toLowerCase();
      filtered = filtered.filter(testCase => 
        testCase.test_case_id.toLowerCase().includes(term) ||
        (testCase.feature && testCase.feature.toLowerCase().includes(term)) ||
        (testCase.test_objective && testCase.test_objective.toLowerCase().includes(term)) ||
        (testCase.procedure && testCase.procedure.toLowerCase().includes(term))
      );
    }
    
    // Filter by types (multi-select)
    if (this.selectedTypes().length > 0) {
      filtered = filtered.filter(tc => this.selectedTypes().includes(tc.test_type || ''));
    }
    
    // Filter by priorities (multi-select)
    if (this.selectedPriorities().length > 0) {
      filtered = filtered.filter(tc => this.selectedPriorities().includes(tc.priority || ''));
    }
    
    // Filter by features (multi-select)
    if (this.selectedFeatures().length > 0) {
      filtered = filtered.filter(tc => this.selectedFeatures().includes(tc.feature || ''));
    }
    
    // Filter by screen IDs (multi-select)
    if (this.selectedScreenIds().length > 0) {
      filtered = filtered.filter(tc => this.selectedScreenIds().includes(tc.screen_id || ''));
    }
    
    // Filter by test suite types (multi-select)
    if (this.selectedTestSuiteTypes().length > 0) {
      filtered = filtered.filter(tc => this.selectedTestSuiteTypes().includes(tc.testsuite_type || ''));
    }
    
    // Filter by requirement types (multi-select)
    if (this.selectedRequirementTypes().length > 0) {
      filtered = filtered.filter(tc => this.selectedRequirementTypes().includes(tc.requirement_type || ''));
    }
    
    return filtered;
  });
  isEditMode = signal(false);
  isSubmitting = signal(false);
  showDeleteModal = signal(false);
  isDeleting = signal(false);
  testCaseToDelete = signal<TestCase | null>(null);
  currentEditingTestCase = signal<TestCase | null>(null);
  searchTerm = signal('');
  selectedTypes = signal<string[]>([]);
  selectedPriorities = signal<string[]>([]);
  selectedFeatures = signal<string[]>([]);
  selectedScreenIds = signal<string[]>([]);
  selectedTestSuiteTypes = signal<string[]>([]);
  selectedRequirementTypes = signal<string[]>([]);
  
  typeSearchTerm = '';
  prioritySearchTerm = '';
  featureSearchTerm = '';
  screenIdSearchTerm = '';
  testSuiteTypeSearchTerm = '';
  requirementTypeSearchTerm = '';
  
  activeFilter = signal<string>('');
  showMoreFilters = signal(false);

  // ---------------------------------------------------------------------
  // Excel bulk-import state. The modal walks the user through three steps:
  //   "select"  → pick files
  //   "mapping" → confirm/edit the auto-detected header → field mapping
  //   "result"  → see the import summary (created/skipped/failed)
  // The mapping step is optional — the "Import (auto-detect)" button on the
  // first step skips it and relies on the backend's HEADER_ALIASES list.
  // ---------------------------------------------------------------------
  showImportModal = signal(false);
  importStep = signal<'select' | 'mapping' | 'result'>('select');
  importFiles = signal<File[]>([]);
  importPreview = signal<TestCaseImportPreview | null>(null);
  importResult = signal<TestCaseImportResult | null>(null);
  importFields = signal<string[]>([]);
  // Effective mapping keyed by raw header → canonical field name.
  importMapping = signal<{ [rawHeader: string]: string }>({});
  // When true, rows whose ID is already in the DB are UPDATEd in place
  // instead of being skipped. Lets users iterate on a spreadsheet without
  // having to manually delete rows between uploads.
  importReplaceDuplicates = signal(false);
  isPreviewing = signal(false);
  isImporting = signal(false);
  importError = signal<string | null>(null);

  testCaseForm: FormGroup;

  constructor() {
    this.testCaseForm = this.formBuilder.group({
      test_case_id: ['', [
        Validators.required,
        Validators.pattern(/^[A-Z]{2}_[A-Z_]+_\d+$/)
      ]],
      title: [''],
      description: [''],
      vehicle_model: [''],
      severity: [''],
      feature: [''],
      priority: [''],
      test_type: [''],
      region: [''],
      test_objective: [''],
      preconditions: [''],
      procedure: [''],
      expected_behavior: [''],
      associated_requirement_id: [''],
      screen_id: [''],
      reference_document: [''],
      dr_applicable_screens: [''],
      dr_id: [''],
      brand: [''],
      vehicle_variant: [''],
      vehicle_specification: [''],
      env_dependency: [''],
      requirement_type: [''],
      regulation: [''],
      testsuite_type: ['']
    });

    // The Browse layout is rendered in-place via <app-split-view> below, so
    // no navigation effect is needed — flipping `currentView` to 'browse'
    // is enough to swap the body while the management page header stays
    // perfectly stable.
  }

  ngOnInit() {
    // Subscribe to the service's test cases observable for real-time updates
    this.testCaseService.testCases$.subscribe(testCases => {
      this.testCases.set(testCases);
    });
    
    // Load initial data
    this.loadTestCases();

    // Honor a `?view=grid|table|browse` query param so other pages can
    // deep-link into the user's preferred layout (e.g. the old /split-view
    // route forwards here with `?view=browse`).
    this.route.queryParams.subscribe(params => {
      const requested = params['view'];
      if (requested === 'grid' || requested === 'table' || requested === 'browse') {
        this.currentView.set(requested);
      }
    });
    
    // Close filter dropdowns when clicking outside. Skip during SSR/prerender
    // where `document` is not defined.
    if (this.isBrowser) {
      document.addEventListener('click', (event) => {
        const target = event.target as HTMLElement;
        if (!target.closest('.filter-panel') && !target.closest('.filter-dropdown') && !target.closest('.filter-btn-blue') && !target.closest('.filter-btn-more')) {
          this.activeFilter.set('');
        }
      });
    }
  }

  loadTestCases() {
    this.isLoading.set(true);
    this.error.set(null);
    
    this.testCaseService.getTestCases().subscribe({
      next: (testCases) => {
        this.testCases.set(testCases);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load test cases');
        this.isLoading.set(false);
        console.error('Error loading test cases:', err);
      }
    });
  }

  toggleMoreFilters() {
    this.showMoreFilters.set(!this.showMoreFilters());
  }
  
  showScreenIdFilter(): boolean {
    return this.activeFilter() === 'screenId';
  }
  
  showTestSuiteTypeFilter(): boolean {
    return this.activeFilter() === 'testsuiteType';
  }
  
  showRequirementTypeFilter(): boolean {
    return this.activeFilter() === 'requirementType';
  }
  
  // Filter management methods
  toggleFilter(filterType: string, event: Event) {
    const button = event.currentTarget as HTMLElement;
    const rect = button.getBoundingClientRect();
    
    if (this.activeFilter() === filterType) {
      this.activeFilter.set('');
    } else {
      this.activeFilter.set(filterType);
      
      // Position the panel immediately using requestAnimationFrame to prevent flicker
      requestAnimationFrame(() => {
        const activePanel = document.querySelector('.filter-panel');
        if (activePanel) {
          const panelEl = activePanel as HTMLElement;
          panelEl.style.top = `${rect.bottom + 4}px`;
          panelEl.style.left = `${rect.left}px`;
          panelEl.style.position = 'fixed';
        }
      });
    }
  }
  
  showTypeFilter(): boolean {
    return this.activeFilter() === 'type';
  }
  
  showPriorityFilter(): boolean {
    return this.activeFilter() === 'priority';
  }
  
  showFeatureFilter(): boolean {
    return this.activeFilter() === 'feature';
  }
  
  getFilterDisplay(type: string): string {
    switch(type) {
      case 'type':
        return this.selectedTypes().length === 0 ? 'any' : this.selectedTypes().join(', ');
      case 'priority':
        return this.selectedPriorities().length === 0 ? 'any' : this.selectedPriorities().join(', ');
      case 'feature':
        return this.selectedFeatures().length === 0 ? 'any' : this.selectedFeatures().join(', ');
      default:
        return 'any';
    }
  }
  
  // Type filter methods
  getTypeOptions(): string[] {
    const options = ['Positive', 'Negative', 'Boundary', 'Performance'];
    if (!this.typeSearchTerm.trim()) return options;
    return options.filter(t => t.toLowerCase().includes(this.typeSearchTerm.toLowerCase()));
  }
  
  toggleType(type: string) {
    const current = this.selectedTypes();
    if (current.includes(type)) {
      this.selectedTypes.set(current.filter(t => t !== type));
    } else {
      this.selectedTypes.set([...current, type]);
    }
  }
  
  isTypeSelected(type: string): boolean {
    return this.selectedTypes().includes(type);
  }
  
  clearTypes() {
    this.selectedTypes.set([]);
  }
  
  getSelectedTypesCount(): number {
    return this.selectedTypes().length;
  }
  
  // Priority filter methods
  getPriorityOptions(): string[] {
    const options = ['P1', 'P2', 'P3'];
    if (!this.prioritySearchTerm.trim()) return options;
    return options.filter(p => p.toLowerCase().includes(this.prioritySearchTerm.toLowerCase()));
  }
  
  togglePriority(priority: string) {
    const current = this.selectedPriorities();
    if (current.includes(priority)) {
      this.selectedPriorities.set(current.filter(p => p !== priority));
    } else {
      this.selectedPriorities.set([...current, priority]);
    }
  }
  
  isPrioritySelected(priority: string): boolean {
    return this.selectedPriorities().includes(priority);
  }
  
  clearPriorities() {
    this.selectedPriorities.set([]);
  }
  
  getSelectedPrioritiesCount(): number {
    return this.selectedPriorities().length;
  }
  
  // Feature filter methods
  getFilteredFeatures(): string[] {
    const allFeatures = this.getUniqueFeatures();
    if (!this.featureSearchTerm.trim()) return allFeatures;
    return allFeatures.filter(f => f.toLowerCase().includes(this.featureSearchTerm.toLowerCase()));
  }
  
  toggleFeature(feature: string) {
    const current = this.selectedFeatures();
    if (current.includes(feature)) {
      this.selectedFeatures.set(current.filter(f => f !== feature));
    } else {
      this.selectedFeatures.set([...current, feature]);
    }
  }
  
  isFeatureSelected(feature: string): boolean {
    return this.selectedFeatures().includes(feature);
  }
  
  clearFeatures() {
    this.selectedFeatures.set([]);
  }
  
  getSelectedFeaturesCount(): number {
    return this.selectedFeatures().length;
  }
  
  clearAllFilters() {
    this.selectedTypes.set([]);
    this.selectedPriorities.set([]);
    this.selectedFeatures.set([]);
    this.selectedScreenIds.set([]);
    this.selectedTestSuiteTypes.set([]);
    this.selectedRequirementTypes.set([]);
    this.activeFilter.set('');
    this.searchTerm.set('');
  }

  // Screen ID filter methods
  getFilteredScreenIds(): string[] {
    const allScreenIds = this.getUniqueScreenIds();
    if (!this.screenIdSearchTerm.trim()) return allScreenIds;
    return allScreenIds.filter(s => s.toLowerCase().includes(this.screenIdSearchTerm.toLowerCase()));
  }

  getUniqueScreenIds(): string[] {
    const screenIds = this.testCases().map(tc => tc.screen_id).filter((s): s is string => s !== undefined && s !== null && s !== '');
    return [...new Set(screenIds)];
  }

  toggleScreenId(screenId: string) {
    const current = this.selectedScreenIds();
    if (current.includes(screenId)) {
      this.selectedScreenIds.set(current.filter(s => s !== screenId));
    } else {
      this.selectedScreenIds.set([...current, screenId]);
    }
  }

  isScreenIdSelected(screenId: string): boolean {
    return this.selectedScreenIds().includes(screenId);
  }

  clearScreenIds() {
    this.selectedScreenIds.set([]);
  }

  getSelectedScreenIdsCount(): number {
    return this.selectedScreenIds().length;
  }

  // TestSuite Type filter methods
  getFilteredTestSuiteTypes(): string[] {
    const options = ['Sanity', 'Smoke', 'Regression', 'Functional', 'Non-Functional'];
    if (!this.testSuiteTypeSearchTerm.trim()) return options;
    return options.filter(t => t.toLowerCase().includes(this.testSuiteTypeSearchTerm.toLowerCase()));
  }

  toggleTestSuiteType(type: string) {
    const current = this.selectedTestSuiteTypes();
    if (current.includes(type)) {
      this.selectedTestSuiteTypes.set(current.filter(t => t !== type));
    } else {
      this.selectedTestSuiteTypes.set([...current, type]);
    }
  }

  isTestSuiteTypeSelected(type: string): boolean {
    return this.selectedTestSuiteTypes().includes(type);
  }

  clearTestSuiteTypes() {
    this.selectedTestSuiteTypes.set([]);
  }

  getSelectedTestSuiteTypesCount(): number {
    return this.selectedTestSuiteTypes().length;
  }

  // Requirement Type filter methods
  getFilteredRequirementTypes(): string[] {
    const options = ['Functional', 'HMI', 'Safety', 'Performance', 'Usability'];
    if (!this.requirementTypeSearchTerm.trim()) return options;
    return options.filter(r => r.toLowerCase().includes(this.requirementTypeSearchTerm.toLowerCase()));
  }

  toggleRequirementType(type: string) {
    const current = this.selectedRequirementTypes();
    if (current.includes(type)) {
      this.selectedRequirementTypes.set(current.filter(t => t !== type));
    } else {
      this.selectedRequirementTypes.set([...current, type]);
    }
  }

  isRequirementTypeSelected(type: string): boolean {
    return this.selectedRequirementTypes().includes(type);
  }

  clearRequirementTypes() {
    this.selectedRequirementTypes.set([]);
  }

  getSelectedRequirementTypesCount(): number {
    return this.selectedRequirementTypes().length;
  }

  getUniqueFeatures(): string[] {
    const features = this.testCases().map(tc => tc.feature).filter((f): f is string => f !== undefined && f !== null && f !== '');
    return [...new Set(features)];
  }

  getPriorityClass(priority: string | undefined): string {
    if (!priority) return 'priority-default';
    const p = priority.toUpperCase();
    if (p.includes('P1') || p.includes('HIGH')) return 'priority-high';
    if (p.includes('P2') || p.includes('MEDIUM')) return 'priority-medium';
    if (p.includes('P3') || p.includes('LOW')) return 'priority-low';
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

  getSeverityClass(severity: string | undefined): string {
    if (!severity) return 'severity-default';
    const s = severity.toLowerCase();
    if (s.includes('block')) return 'severity-blocker';
    if (s.includes('crit')) return 'severity-critical';
    if (s.includes('major') || s.includes('high')) return 'severity-major';
    if (s.includes('minor') || s.includes('med')) return 'severity-minor';
    if (s.includes('triv') || s.includes('low')) return 'severity-trivial';
    return 'severity-default';
  }

  // ---------------------------------------------------------------------
  // Excel bulk-import flow
  // ---------------------------------------------------------------------
  openImportModal() {
    this.resetImportState();
    this.showImportModal.set(true);
    // Lazily fetch the canonical field list once per modal open so the
    // mapping <select>s have the latest server-side allow-list.
    if (this.importFields().length === 0) {
      this.testCaseService.getImportFields().subscribe({
        next: (res) => this.importFields.set(res.fields || []),
        error: () => {
          // Fall back to a sensible hard-coded list if the endpoint is
          // unreachable — the user can still pick from these.
          this.importFields.set([
            'test_case_id', 'title', 'description', 'vehicle_model', 'severity',
            'feature', 'priority', 'test_type', 'region', 'brand',
            'vehicle_variant', 'vehicle_specification', 'env_dependency',
            'test_objective', 'preconditions', 'procedure', 'expected_behavior',
            'associated_requirement_id', 'screen_id', 'reference_document',
            'requirement_type', 'regulation', 'testsuite_type',
          ]);
        }
      });
    }
  }

  closeImportModal() {
    this.showImportModal.set(false);
    this.resetImportState();
  }

  private resetImportState() {
    this.importStep.set('select');
    this.importFiles.set([]);
    this.importPreview.set(null);
    this.importResult.set(null);
    this.importMapping.set({});
    this.importReplaceDuplicates.set(false);
    this.importError.set(null);
    this.isPreviewing.set(false);
    this.isImporting.set(false);
  }

  onImportFilesSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) {
      this.importFiles.set([]);
      return;
    }
    this.importFiles.set(Array.from(input.files));
    this.importError.set(null);
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  /** STEP 1 → STEP 2: dry-run the first file to populate the mapping editor. */
  previewSelectedFile() {
    const files = this.importFiles();
    if (files.length === 0) return;
    this.isPreviewing.set(true);
    this.importError.set(null);
    // Preview only the first file — mapping is shared across all files in
    // the batch, which matches the common case of "same vendor, multiple
    // monthly exports".
    this.testCaseService.previewImport(files[0]).subscribe({
      next: (preview) => {
        this.importPreview.set(preview);
        // Seed the mapping from the backend's suggestions so the dropdowns
        // are pre-filled with sensible defaults.
        const seed: { [raw: string]: string } = {};
        preview.sheets.forEach((sheet) => {
          Object.entries(sheet.suggested_mapping || {}).forEach(([raw, field]) => {
            if (field) seed[raw] = field;
          });
        });
        this.importMapping.set(seed);
        this.importStep.set('mapping');
        this.isPreviewing.set(false);
      },
      error: (err) => {
        this.importError.set(this.formatHttpError(err, 'Preview failed'));
        this.isPreviewing.set(false);
      }
    });
  }

  /** STEP 1 quick path: skip mapping and rely on auto-detection. */
  importNow() {
    const files = this.importFiles();
    if (files.length === 0) return;
    this.runImport(files);
  }

  /** STEP 2: submit the import with the user's confirmed mapping. */
  importWithMapping() {
    const files = this.importFiles();
    if (files.length === 0) return;
    this.runImport(files, this.importMapping());
  }

  private runImport(files: File[], mapping?: { [k: string]: string }) {
    this.isImporting.set(true);
    this.importError.set(null);
    const strategy: TestCaseImportDuplicateStrategy =
      this.importReplaceDuplicates() ? 'replace' : 'skip';
    this.testCaseService.importTestCases(files, mapping, strategy).subscribe({
      next: (result) => {
        this.importResult.set(result);
        this.importStep.set('result');
        this.isImporting.set(false);
      },
      error: (err) => {
        this.importError.set(this.formatHttpError(err, 'Import failed'));
        this.isImporting.set(false);
      }
    });
  }

  backToSelect() {
    this.importStep.set('select');
    this.importPreview.set(null);
    this.importResult.set(null);
    this.importError.set(null);
  }

  getMappingValue(rawHeader: string): string {
    return this.importMapping()[rawHeader] || '';
  }

  setMappingValue(rawHeader: string, value: string) {
    const next = { ...this.importMapping() };
    if (value) {
      next[rawHeader] = value;
    } else {
      delete next[rawHeader];
    }
    this.importMapping.set(next);
  }

  sampleValueFor(sheet: TestCaseImportSheetPreview, columnIndex: number): string | null {
    for (const row of sheet.sample_rows) {
      const v = row[columnIndex];
      if (v !== null && v !== undefined && String(v).trim() !== '') {
        return String(v);
      }
    }
    return null;
  }

  private formatHttpError(err: any, fallback: string): string {
    if (!err) return fallback;
    if (err.error?.message) return err.error.message;
    if (err.message) return err.message;
    return fallback;
  }

  openCreateModal() {
    this.isEditMode.set(false);
    this.testCaseForm.reset();
    this.showModal.set(true);
  }

  openEditModal(testCase: TestCase) {
    this.isEditMode.set(true);
    this.currentEditingTestCase.set(testCase);
    this.testCaseForm.patchValue({
      test_case_id: testCase.test_case_id,
      title: testCase.title || '',
      description: testCase.description || '',
      vehicle_model: testCase.vehicle_model || '',
      severity: testCase.severity || '',
      feature: testCase.feature || '',
      priority: testCase.priority || '',
      test_type: testCase.test_type || '',
      region: testCase.region || '',
      test_objective: testCase.test_objective || '',
      preconditions: testCase.preconditions || '',
      procedure: testCase.procedure || '',
      expected_behavior: testCase.expected_behavior || '',
      associated_requirement_id: testCase.associated_requirement_id || '',
      screen_id: testCase.screen_id || '',
      reference_document: testCase.reference_document || '',
      dr_applicable_screens: testCase.dr_applicable_screens || '',
      dr_id: testCase.dr_id || '',
      brand: testCase.brand || '',
      vehicle_variant: testCase.vehicle_variant || '',
      vehicle_specification: testCase.vehicle_specification || '',
      env_dependency: testCase.env_dependency || '',
      requirement_type: testCase.requirement_type || '',
      regulation: testCase.regulation || '',
      testsuite_type: testCase.testsuite_type || ''
    });
    this.showModal.set(true);
  }

  closeModal() {
    this.showModal.set(false);
    this.testCaseForm.reset();
    this.isSubmitting.set(false);
    this.currentEditingTestCase.set(null);
  }

  onSubmit() {
    if (this.testCaseForm.invalid) {
      this.markFormGroupTouched();
      return;
    }

    this.isSubmitting.set(true);
    const formData = this.testCaseForm.value;

    if (this.isEditMode()) {
      const currentTestCase = this.currentEditingTestCase();
      if (currentTestCase?.test_case_id) {
        const updateData: TestCaseUpdateRequest = {
          test_case_id: formData.test_case_id,
          title: formData.title,
          description: formData.description,
          vehicle_model: formData.vehicle_model,
          severity: formData.severity,
          feature: formData.feature,
          priority: formData.priority,
          test_type: formData.test_type,
          region: formData.region,
          test_objective: formData.test_objective,
          preconditions: formData.preconditions,
          procedure: formData.procedure,
          expected_behavior: formData.expected_behavior,
          associated_requirement_id: formData.associated_requirement_id,
          screen_id: formData.screen_id,
          reference_document: formData.reference_document,
          dr_applicable_screens: formData.dr_applicable_screens,
          dr_id: formData.dr_id,
          brand: formData.brand,
          vehicle_variant: formData.vehicle_variant,
          vehicle_specification: formData.vehicle_specification,
          env_dependency: formData.env_dependency,
          requirement_type: formData.requirement_type,
          regulation: formData.regulation,
          testsuite_type: formData.testsuite_type
        };

        this.testCaseService.updateTestCase(currentTestCase.test_case_id, updateData).subscribe({
          next: (updatedTestCase) => {
            if (updatedTestCase) {
              this.closeModal();
              // Service will automatically update the observable
            } else {
              this.error.set('Failed to update test case');
            }
            this.isSubmitting.set(false);
          },
          error: (err) => {
            this.error.set('Failed to update test case');
            this.isSubmitting.set(false);
            console.error('Error updating test case:', err);
          }
        });
      } else {
        this.error.set('No test case selected for editing');
        this.isSubmitting.set(false);
      }
    } else {
      const createData: TestCaseCreateRequest = {
        test_case_id: formData.test_case_id,
        title: formData.title,
        description: formData.description,
        vehicle_model: formData.vehicle_model,
        severity: formData.severity,
        feature: formData.feature,
        priority: formData.priority,
        test_type: formData.test_type,
        region: formData.region,
        test_objective: formData.test_objective,
        preconditions: formData.preconditions,
        procedure: formData.procedure,
        expected_behavior: formData.expected_behavior,
        associated_requirement_id: formData.associated_requirement_id,
        screen_id: formData.screen_id,
        reference_document: formData.reference_document,
        dr_applicable_screens: formData.dr_applicable_screens,
        dr_id: formData.dr_id,
        brand: formData.brand,
        vehicle_variant: formData.vehicle_variant,
        vehicle_specification: formData.vehicle_specification,
        env_dependency: formData.env_dependency,
        requirement_type: formData.requirement_type,
        regulation: formData.regulation,
        testsuite_type: formData.testsuite_type
      };

      this.testCaseService.createTestCase(createData).subscribe({
        next: (newTestCase) => {
          if (newTestCase) {
            this.closeModal();
            // Service will automatically update the observable
          } else {
            this.error.set('Failed to create test case');
          }
          this.isSubmitting.set(false);
        },
        error: (err) => {
          this.error.set('Failed to create test case');
          this.isSubmitting.set(false);
          console.error('Error creating test case:', err);
        }
      });
    }
  }

  confirmDelete(testCase: TestCase) {
    this.testCaseToDelete.set(testCase);
    this.showDeleteModal.set(true);
  }

  cancelDelete() {
    this.showDeleteModal.set(false);
    this.testCaseToDelete.set(null);
    this.isDeleting.set(false);
  }

  deleteTestCase() {
    const testCase = this.testCaseToDelete();
    if (!testCase?.test_case_id) return;

    this.isDeleting.set(true);
    this.testCaseService.deleteTestCase(testCase.test_case_id).subscribe({
      next: (success) => {
        if (success) {
          this.cancelDelete();
          // Service will automatically update the observable
        } else {
          this.error.set('Failed to delete test case');
        }
        this.isDeleting.set(false);
      },
      error: (err) => {
        this.error.set('Failed to delete test case');
        this.isDeleting.set(false);
        console.error('Error deleting test case:', err);
      }
    });
  }

  showDeleteModalSignal(): boolean {
    return this.showDeleteModal();
  }

  navigateToDetail(id: string | number) {
    this.router.navigate(['/test-cases', id]);
  }

  private markFormGroupTouched() {
    Object.keys(this.testCaseForm.controls).forEach(key => {
      const control = this.testCaseForm.get(key);
      control?.markAsTouched();
    });
  }
}
