import { Component, OnInit, inject, signal, computed, effect, PLATFORM_ID } from '@angular/core';
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
          <a
            class="add-btn import-btn"
            routerLink="/test-cases/import"
            title="Bulk-import test cases — drag & drop spreadsheets, preview every sheet, save column-mapping presets.">
            <i class="icon-upload"></i>
            Import Test Cases
          </a>
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
              Feature ▼
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
            <button class="filter-btn-blue" [class.active]="showPriorityFilter()" (click)="toggleFilter('priority', $event)">
              Priority ▼
              <span class="filter-count" *ngIf="selectedPriorities().length > 0">+{{ selectedPriorities().length }}</span>
            </button>
          </div>
          <div class="filter-dropdown" (click)="$event.stopPropagation()">
            <button class="filter-btn-blue" [class.active]="showSeverityFilter()" (click)="toggleFilter('severity', $event)">
              Severity ▼
              <span class="filter-count" *ngIf="selectedSeverities().length > 0">+{{ selectedSeverities().length }}</span>
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
          <button
            class="advanced-toggle-btn"
            [class.active]="showAdvancedFilters()"
            (click)="toggleAdvancedFilters()"
            title="Toggle advanced filters">
            More Filters
            <span *ngIf="advancedFilterCount() > 0" class="filter-count">+{{ advancedFilterCount() }}</span>
          </button>
          <button class="clear-filters-btn" *ngIf="hasActiveFilters()" (click)="clearAllFilters()">Clear filters</button>
        </div>

        <!-- Advanced filters row -->
        <div *ngIf="showAdvancedFilters()" class="advanced-filters">
          <div class="filter-tabs">
            <div class="filter-dropdown" (click)="$event.stopPropagation()">
              <button class="filter-btn-blue" [class.active]="showVehicleModelFilter()" (click)="toggleFilter('vehicleModel', $event)">
                Vehicle Model ▼
                <span class="filter-count" *ngIf="selectedVehicleModels().length > 0">+{{ selectedVehicleModels().length }}</span>
              </button>
            </div>
            <div class="filter-dropdown" (click)="$event.stopPropagation()">
              <button class="filter-btn-blue" [class.active]="showRegionFilter()" (click)="toggleFilter('region', $event)">
                Region ▼
                <span class="filter-count" *ngIf="selectedRegions().length > 0">+{{ selectedRegions().length }}</span>
              </button>
            </div>
            <div class="filter-dropdown" (click)="$event.stopPropagation()">
              <button class="filter-btn-blue" [class.active]="showBrandFilter()" (click)="toggleFilter('brand', $event)">
                Brand ▼
                <span class="filter-count" *ngIf="selectedBrands().length > 0">+{{ selectedBrands().length }}</span>
              </button>
            </div>
            <label class="adv-field">
              <span class="adv-label">Created From</span>
              <input type="date" class="adv-input" [ngModel]="dateFrom()" (ngModelChange)="dateFrom.set($event)">
            </label>
            <label class="adv-field">
              <span class="adv-label">Created To</span>
              <input type="date" class="adv-input" [ngModel]="dateTo()" (ngModelChange)="dateTo.set($event)">
            </label>
            <label class="adv-field">
              <span class="adv-label">Sort By</span>
              <div class="sort-control">
                <select class="adv-input sort-select" [ngModel]="sortBy()" (ngModelChange)="sortBy.set($event)">
                  <option value="updated_at">Last Updated</option>
                  <option value="created_at">Created Date</option>
                  <option value="test_case_id">Test Case ID</option>
                  <option value="priority">Priority</option>
                  <option value="severity">Severity</option>
                  <option value="title">Title</option>
                </select>
                <button class="sort-dir-btn" (click)="toggleSortDir()" [title]="sortDir() === 'asc' ? 'Ascending' : 'Descending'">
                  {{ sortDir() === 'asc' ? '▲' : '▼' }}
                </button>
              </div>
            </label>
          </div>
        </div>

        <!-- Active filter chips -->
        <div *ngIf="hasActiveFilters()" class="active-filters">
          <span class="active-filters-label">Active:</span>
          <span *ngIf="searchTerm().trim()" class="active-chip">
            Search: "{{ searchTerm() }}" <button (click)="searchTerm.set('')">✕</button>
          </span>
          <span *ngFor="let f of selectedFeatures()" class="active-chip">
            Feature: {{ f }} <button (click)="toggleFeature(f)">✕</button>
          </span>
          <span *ngFor="let s of selectedScreenIds()" class="active-chip">
            Screen: {{ s }} <button (click)="toggleScreenId(s)">✕</button>
          </span>
          <span *ngFor="let t of selectedTypes()" class="active-chip">
            Type: {{ t }} <button (click)="toggleType(t)">✕</button>
          </span>
          <span *ngFor="let p of selectedPriorities()" class="active-chip">
            Priority: {{ p }} <button (click)="togglePriority(p)">✕</button>
          </span>
          <span *ngFor="let sv of selectedSeverities()" class="active-chip">
            Severity: {{ sv }} <button (click)="toggleSeverity(sv)">✕</button>
          </span>
          <span *ngFor="let tt of selectedTestSuiteTypes()" class="active-chip">
            TestSuite: {{ tt }} <button (click)="toggleTestSuiteType(tt)">✕</button>
          </span>
          <span *ngFor="let rt of selectedRequirementTypes()" class="active-chip">
            Req. Type: {{ rt }} <button (click)="toggleRequirementType(rt)">✕</button>
          </span>
          <span *ngFor="let vm of selectedVehicleModels()" class="active-chip">
            Vehicle: {{ vm }} <button (click)="toggleVehicleModel(vm)">✕</button>
          </span>
          <span *ngFor="let rg of selectedRegions()" class="active-chip">
            Region: {{ rg }} <button (click)="toggleRegion(rg)">✕</button>
          </span>
          <span *ngFor="let br of selectedBrands()" class="active-chip">
            Brand: {{ br }} <button (click)="toggleBrand(br)">✕</button>
          </span>
          <span *ngIf="dateFrom()" class="active-chip">
            From: {{ dateFrom() }} <button (click)="dateFrom.set('')">✕</button>
          </span>
          <span *ngIf="dateTo()" class="active-chip">
            To: {{ dateTo() }} <button (click)="dateTo.set('')">✕</button>
          </span>
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

        <!-- Severity Filter Dropdown -->
        <div class="filter-panel" *ngIf="showSeverityFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header"><span>Severity = (equals)</span></div>
          <input type="text" placeholder="Search Severity" class="filter-search" [(ngModel)]="severitySearchTerm">
          <div class="filter-options">
            <label *ngFor="let s of getFilteredSeverities()" class="filter-option">
              <input type="checkbox" [checked]="isSeveritySelected(s)" (change)="toggleSeverity(s)">
              <span class="filter-label">{{ s }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearSeverities()">Clear selection</button>
            <span class="filter-count-info">{{ selectedSeverities().length }} of {{ getFilteredSeverities().length }}</span>
          </div>
        </div>

        <!-- Vehicle Model Filter Dropdown -->
        <div class="filter-panel" *ngIf="showVehicleModelFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header"><span>Vehicle Model = (equals)</span></div>
          <input type="text" placeholder="Search Vehicle Model" class="filter-search" [(ngModel)]="vehicleModelSearchTerm">
          <div class="filter-options">
            <label *ngFor="let v of getFilteredVehicleModels()" class="filter-option">
              <input type="checkbox" [checked]="isVehicleModelSelected(v)" (change)="toggleVehicleModel(v)">
              <span class="filter-label">{{ v }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearVehicleModels()">Clear selection</button>
            <span class="filter-count-info">{{ selectedVehicleModels().length }} of {{ getFilteredVehicleModels().length }}</span>
          </div>
        </div>

        <!-- Region Filter Dropdown -->
        <div class="filter-panel" *ngIf="showRegionFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header"><span>Region = (equals)</span></div>
          <input type="text" placeholder="Search Region" class="filter-search" [(ngModel)]="regionSearchTerm">
          <div class="filter-options">
            <label *ngFor="let r of getFilteredRegions()" class="filter-option">
              <input type="checkbox" [checked]="isRegionSelected(r)" (change)="toggleRegion(r)">
              <span class="filter-label">{{ r }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearRegions()">Clear selection</button>
            <span class="filter-count-info">{{ selectedRegions().length }} of {{ getFilteredRegions().length }}</span>
          </div>
        </div>

        <!-- Brand Filter Dropdown -->
        <div class="filter-panel" *ngIf="showBrandFilter()" (click)="$event.stopPropagation()">
          <div class="filter-panel-header"><span>Brand = (equals)</span></div>
          <input type="text" placeholder="Search Brand" class="filter-search" [(ngModel)]="brandSearchTerm">
          <div class="filter-options">
            <label *ngFor="let b of getFilteredBrands()" class="filter-option">
              <input type="checkbox" [checked]="isBrandSelected(b)" (change)="toggleBrand(b)">
              <span class="filter-label">{{ b }}</span>
            </label>
          </div>
          <div class="filter-footer">
            <button class="filter-clear" (click)="clearBrands()">Clear selection</button>
            <span class="filter-count-info">{{ selectedBrands().length }} of {{ getFilteredBrands().length }}</span>
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
          <p *ngIf="hasActiveFilters()">
            No test cases match your filter criteria.
          </p>
          <p *ngIf="!hasActiveFilters()">
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
              <tr *ngFor="let tc of pagedTestCases()" (click)="navigateToDetail(tc.test_case_id)" style="cursor: pointer;">
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
                <td>{{ mv(tc.feature) }}</td>
                <td (click)="$event.stopPropagation()">
                  <div class="actions">
                    <button class="btn-edit" (click)="navigateToDetailEdit(tc.test_case_id)" title="Edit" aria-label="Edit">
                      <svg class="action-icon" viewBox="0 0 24 24" width="16" height="16"
                           fill="none" stroke="currentColor" stroke-width="2"
                           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M12 20h9"/>
                        <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4Z"/>
                      </svg>
                    </button>
                    <button class="btn-delete" (click)="confirmDelete(tc)" title="Delete" aria-label="Delete">
                      <svg class="action-icon" viewBox="0 0 24 24" width="16" height="16"
                           fill="none" stroke="currentColor" stroke-width="2"
                           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                        <path d="M10 11v6"/>
                        <path d="M14 11v6"/>
                        <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Grid View -->
        <div *ngIf="filteredTestCases().length > 0 && currentView() === 'grid'" class="requirements-grid">
          <div *ngFor="let tc of pagedTestCases()" class="requirement-card" (click)="navigateToDetail(tc.test_case_id)">
            <div class="card-header">
              <span class="req-id">{{ tc.test_case_id }}</span>
              <span class="priority-badge" [class]="getPriorityClass(tc.priority)">
                {{ tc.priority || 'P3' }}
              </span>
            </div>
            <h3 class="card-title">{{ tc.title || tc.test_objective || 'Test Case' }}</h3>
            <p class="card-description" *ngIf="tc.vehicle_model">🚗 {{ tc.vehicle_model }}<span *ngIf="tc.severity"> · {{ tc.severity }}</span></p>
            <p class="card-description" *ngIf="mv(tc.feature, '') as f">Feature: {{ f }}</p>
            <p class="card-description" *ngIf="tc.description || tc.preconditions">{{ tc.description || tc.preconditions }}</p>
            
            <div class="card-footer">
              <span class="status-badge" [class]="getTypeClass(tc.test_type)">
                {{ tc.test_type || 'N/A' }}
              </span>
              <span class="assignee" *ngIf="mv(tc.feature, '') as f">👤 {{ f }}</span>
            </div>
            <div class="card-actions" (click)="$event.stopPropagation()">
              <button class="btn-edit" (click)="navigateToDetailEdit(tc.test_case_id)" title="Edit" aria-label="Edit">
                <svg class="action-icon" viewBox="0 0 24 24" width="16" height="16"
                     fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 20h9"/>
                  <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4Z"/>
                </svg>
              </button>
              <button class="btn-delete" (click)="confirmDelete(tc)" title="Delete" aria-label="Delete">
                <svg class="action-icon" viewBox="0 0 24 24" width="16" height="16"
                     fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                  <path d="M10 11v6"/>
                  <path d="M14 11v6"/>
                  <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Pagination Controls (grid/table views only) -->
        <div *ngIf="filteredTestCases().length > 0 && currentView() !== 'browse'" class="pagination-bar">
          <div class="pagination-info">
            Showing <strong>{{ pageStartIndex() }}</strong>–<strong>{{ pageEndIndex() }}</strong>
            of <strong>{{ filteredTestCases().length }}</strong> test cases
          </div>
          <div class="pagination-controls">
            <label class="page-size-label">
              Per page
              <select class="page-size-select"
                      [value]="pageSize()"
                      (change)="onPageSizeChange($any($event.target).value)">
                <option [value]="10">10</option>
                <option [value]="20">20</option>
                <option [value]="50">50</option>
                <option [value]="100">100</option>
              </select>
            </label>
            <button class="page-btn"
                    (click)="prevPage()"
                    [disabled]="currentPage() === 1"
                    aria-label="Previous page">‹ Prev</button>
            <button *ngFor="let p of pageNumbers()"
                    class="page-btn page-num"
                    [class.active]="p === currentPage()"
                    [disabled]="p === '…'"
                    (click)="goToPage(p)">{{ p }}</button>
            <button class="page-btn"
                    (click)="nextPage()"
                    [disabled]="currentPage() === totalPages()"
                    aria-label="Next page">Next ›</button>
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
      background: #fce8e6;
      border: 1px solid #f5c6c4;
      border-radius: 4px;
      color: #c5221f;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
    }

    .clear-filters-btn:hover {
      background: #fad2cf;
    }

    .advanced-toggle-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border: 1px dashed #1a73e8;
      border-radius: 4px;
      background: #fff;
      color: #1a73e8;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
      white-space: nowrap;
    }
    .advanced-toggle-btn:hover {
      background: #e8f0fe;
    }
    .advanced-toggle-btn.active {
      background: #1a73e8;
      color: white;
      border-style: solid;
    }
    .advanced-toggle-btn.active .filter-count {
      background: #fff;
      color: #1a73e8;
    }

    .advanced-filters {
      padding-top: 8px;
      margin-top: 4px;
      border-top: 1px dashed #dadce0;
    }

    .adv-field {
      display: inline-flex;
      flex-direction: column;
      gap: 4px;
      min-width: 140px;
    }
    .adv-label {
      font-size: 11px;
      font-weight: 600;
      color: #5f6368;
      text-transform: uppercase;
      letter-spacing: 0.4px;
    }
    .adv-input {
      padding: 7px 10px;
      border: 1px solid #dadce0;
      border-radius: 4px;
      font-size: 13px;
      background: white;
    }
    .adv-input:focus {
      outline: none;
      border-color: #1a73e8;
      box-shadow: 0 0 0 2px rgba(26,115,232,0.15);
    }
    .sort-control {
      display: flex;
      gap: 4px;
    }
    .sort-select { flex: 1; }
    .sort-dir-btn {
      width: 32px;
      border: 1px solid #dadce0;
      background: white;
      border-radius: 4px;
      cursor: pointer;
      color: #3c4043;
      transition: all 0.15s;
    }
    .sort-dir-btn:hover {
      background: #f1f3f4;
      border-color: #1a73e8;
      color: #1a73e8;
    }

    .active-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      padding-top: 8px;
      border-top: 1px solid #f0f0f0;
      margin-top: 4px;
    }
    .active-filters-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      color: #5f6368;
      letter-spacing: 0.4px;
    }
    .active-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 4px 4px 10px;
      background: #e8f0fe;
      color: #1a73e8;
      border-radius: 14px;
      font-size: 12px;
      font-weight: 500;
    }
    .active-chip button {
      background: transparent;
      border: none;
      color: #1a73e8;
      cursor: pointer;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      font-size: 11px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
    }
    .active-chip button:hover {
      background: rgba(26, 115, 232, 0.18);
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

    /* Pagination bar */
    .pagination-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 4px 4px 4px;
      margin-top: 16px;
      border-top: 1px solid #e0e0e0;
      flex-wrap: wrap;
    }
    .pagination-info {
      color: #5f6368;
      font-size: 13px;
    }
    .pagination-controls {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .page-size-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #5f6368;
      font-size: 13px;
      margin-right: 8px;
    }
    .page-size-select {
      padding: 4px 8px;
      border: 1px solid #dadce0;
      border-radius: 4px;
      font-size: 13px;
      background: #fff;
      cursor: pointer;
    }
    .page-btn {
      min-width: 34px;
      height: 32px;
      padding: 0 10px;
      border: 1px solid #dadce0;
      background: #fff;
      color: #202124;
      font-size: 13px;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .page-btn:hover:not(:disabled):not(.active) {
      background: #f1f3f4;
      border-color: #c3c8d0;
    }
    .page-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    .page-btn.active {
      background: #1a73e8;
      color: #fff;
      border-color: #1a73e8;
      font-weight: 600;
    }
  `]
})
export class TestCaseManagementComponent implements OnInit {
  private testCaseService = inject(TestCaseService);
  private formBuilder = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private readonly isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  /**
   * Render a multi-value test-case field (e.g. feature, brand, region)
   * as a human-readable string for the table / grid templates.
   * Returns the supplied placeholder when the value is empty.
   */
  mv(value: any, placeholder: string = '-'): string {
    const text = TestCaseService.mvDisplay(value);
    return text === '' ? placeholder : text;
  }

  // Signals for reactive state management
  testCases = signal<TestCase[]>([]);
  isLoading = signal(false);
  error = signal<string | null>(null);
  showModal = signal(false);
  currentView = signal<'grid' | 'table' | 'browse'>('table');
  
  // Computed signal for filtered test cases
  filteredTestCases = computed(() => {
    let filtered = this.testCases();

    if (this.searchTerm().trim()) {
      const term = this.searchTerm().toLowerCase();
      // Multi-value fields (feature, brand, ...) may arrive as arrays;
      // mvDisplay() flattens them to a comma-joined string for substring
      // matching so the search box keeps working post-schema-change.
      filtered = filtered.filter(testCase =>
        testCase.test_case_id.toLowerCase().includes(term) ||
        TestCaseService.mvDisplay(testCase.feature).toLowerCase().includes(term) ||
        (testCase.test_objective && testCase.test_objective.toLowerCase().includes(term)) ||
        (testCase.procedure && testCase.procedure.toLowerCase().includes(term)) ||
        (testCase.title && testCase.title.toLowerCase().includes(term)) ||
        (testCase.description && testCase.description.toLowerCase().includes(term)) ||
        (testCase.vehicle_model && testCase.vehicle_model.toLowerCase().includes(term)) ||
        TestCaseService.mvDisplay(testCase.brand).toLowerCase().includes(term)
      );
    }

    // Multi-value matchers: keep a row when ANY of its values is in the
    // selected set. Single-value columns (test_type, priority, severity,
    // vehicle_model, requirement_type) keep their exact-match semantics.
    const anyMatch = (sel: string[], v: any) =>
      TestCaseService.mvArray(v).some(item => sel.includes(item));

    if (this.selectedTypes().length > 0) {
      filtered = filtered.filter(tc => this.selectedTypes().includes(tc.test_type || ''));
    }
    if (this.selectedPriorities().length > 0) {
      filtered = filtered.filter(tc => this.selectedPriorities().includes(tc.priority || ''));
    }
    if (this.selectedFeatures().length > 0) {
      filtered = filtered.filter(tc => anyMatch(this.selectedFeatures(), tc.feature));
    }
    if (this.selectedScreenIds().length > 0) {
      filtered = filtered.filter(tc => anyMatch(this.selectedScreenIds(), tc.screen_id));
    }
    if (this.selectedTestSuiteTypes().length > 0) {
      filtered = filtered.filter(tc => anyMatch(this.selectedTestSuiteTypes(), tc.testsuite_type));
    }
    if (this.selectedRequirementTypes().length > 0) {
      filtered = filtered.filter(tc => this.selectedRequirementTypes().includes(tc.requirement_type || ''));
    }
    if (this.selectedSeverities().length > 0) {
      filtered = filtered.filter(tc => this.selectedSeverities().includes(tc.severity || ''));
    }
    if (this.selectedVehicleModels().length > 0) {
      filtered = filtered.filter(tc => this.selectedVehicleModels().includes(tc.vehicle_model || ''));
    }
    if (this.selectedRegions().length > 0) {
      filtered = filtered.filter(tc => anyMatch(this.selectedRegions(), tc.region));
    }
    if (this.selectedBrands().length > 0) {
      filtered = filtered.filter(tc => anyMatch(this.selectedBrands(), tc.brand));
    }

    const from = this.dateFrom();
    const to = this.dateTo();
    if (from || to) {
      const fromTs = from ? new Date(from).getTime() : -Infinity;
      const toTs = to ? new Date(to).getTime() + 86399999 : Infinity;
      filtered = filtered.filter(tc => {
        const created = (tc as any).created_at;
        if (!created) return false;
        const ts = new Date(created).getTime();
        return ts >= fromTs && ts <= toTs;
      });
    }

    const sortBy = this.sortBy();
    const dir = this.sortDir() === 'asc' ? 1 : -1;
    const priorityOrder: Record<string, number> = { P1: 1, P2: 2, P3: 3, P4: 4 };
    const severityOrder: Record<string, number> = {
      Blocker: 1, Critical: 2, Major: 3, Minor: 4, Trivial: 5
    };
    filtered = [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'priority':
          cmp = (priorityOrder[a.priority || ''] ?? 99) - (priorityOrder[b.priority || ''] ?? 99);
          break;
        case 'severity':
          cmp = (severityOrder[a.severity || ''] ?? 99) - (severityOrder[b.severity || ''] ?? 99);
          break;
        case 'test_case_id':
          cmp = (a.test_case_id || '').localeCompare(b.test_case_id || '', undefined, { numeric: true });
          break;
        case 'title':
          cmp = (a.title || a.test_objective || '').localeCompare(b.title || b.test_objective || '');
          break;
        case 'created_at':
          cmp = new Date((a as any).created_at || 0).getTime() - new Date((b as any).created_at || 0).getTime();
          break;
        case 'updated_at':
        default:
          cmp = new Date((a as any).updated_at || (a as any).created_at || 0).getTime()
              - new Date((b as any).updated_at || (b as any).created_at || 0).getTime();
      }
      return cmp * dir;
    });

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
  selectedSeverities = signal<string[]>([]);
  selectedVehicleModels = signal<string[]>([]);
  selectedRegions = signal<string[]>([]);
  selectedBrands = signal<string[]>([]);
  dateFrom = signal<string>('');
  dateTo = signal<string>('');
  sortBy = signal<'updated_at' | 'created_at' | 'test_case_id' | 'priority' | 'severity' | 'title'>('updated_at');
  sortDir = signal<'asc' | 'desc'>('desc');
  showAdvancedFilters = signal<boolean>(false);

  typeSearchTerm = '';
  prioritySearchTerm = '';
  featureSearchTerm = '';
  screenIdSearchTerm = '';
  testSuiteTypeSearchTerm = '';
  requirementTypeSearchTerm = '';
  severitySearchTerm = '';
  vehicleModelSearchTerm = '';
  regionSearchTerm = '';
  brandSearchTerm = '';

  activeFilter = signal<string>('');

  // Pagination state — 20 per page, applied to grid/table views (Browse uses
  // the split-view which renders its own virtualized list).
  pageSize = signal(10);
  currentPage = signal(1);
  totalPages = computed(() => Math.max(1, Math.ceil(this.filteredTestCases().length / this.pageSize())));
  pagedTestCases = computed(() => {
    const all = this.filteredTestCases();
    const size = this.pageSize();
    const page = Math.min(this.currentPage(), Math.max(1, Math.ceil(all.length / size)));
    const start = (page - 1) * size;
    return all.slice(start, start + size);
  });
  pageStartIndex = computed(() => {
    if (this.filteredTestCases().length === 0) return 0;
    return (this.currentPage() - 1) * this.pageSize() + 1;
  });
  pageEndIndex = computed(() =>
    Math.min(this.currentPage() * this.pageSize(), this.filteredTestCases().length)
  );
  pageNumbers = computed<(number | '…')[]>(() => {
    const total = this.totalPages();
    const current = this.currentPage();
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages: (number | '…')[] = [1];
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    if (start > 2) pages.push('…');
    for (let i = start; i <= end; i++) pages.push(i);
    if (end < total - 1) pages.push('…');
    pages.push(total);
    return pages;
  });

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
      vehicle_mode: [''],
      env_dependency: [''],
      requirement_type: [''],
      regulation: [''],
      testsuite_type: ['']
    });

    // The Browse layout is rendered in-place via <app-split-view> below, so
    // no navigation effect is needed — flipping `currentView` to 'browse'
    // is enough to swap the body while the management page header stays
    // perfectly stable.

    // Reset to first page whenever the active filter set changes so the
    // user isn't stranded on an empty trailing page.
    effect(() => {
      this.searchTerm();
      this.selectedTypes();
      this.selectedPriorities();
      this.selectedFeatures();
      this.selectedScreenIds();
      this.selectedTestSuiteTypes();
      this.selectedRequirementTypes();
      this.selectedSeverities();
      this.selectedVehicleModels();
      this.selectedRegions();
      this.selectedBrands();
      this.dateFrom();
      this.dateTo();
      this.sortBy();
      this.sortDir();
      this.currentPage.set(1);
    });

    // Clamp the current page if the filtered list shrinks below it (e.g.
    // after deleting items on the last page).
    effect(() => {
      const total = this.totalPages();
      if (this.currentPage() > total) this.currentPage.set(total);
    });
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
        if (!target.closest('.filter-panel') && !target.closest('.filter-dropdown') && !target.closest('.filter-btn-blue')) {
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
    this.selectedSeverities.set([]);
    this.selectedVehicleModels.set([]);
    this.selectedRegions.set([]);
    this.selectedBrands.set([]);
    this.dateFrom.set('');
    this.dateTo.set('');
    this.activeFilter.set('');
    this.searchTerm.set('');
  }

  hasActiveFilters(): boolean {
    return !!this.searchTerm().trim()
      || this.selectedTypes().length > 0
      || this.selectedPriorities().length > 0
      || this.selectedFeatures().length > 0
      || this.selectedScreenIds().length > 0
      || this.selectedTestSuiteTypes().length > 0
      || this.selectedRequirementTypes().length > 0
      || this.selectedSeverities().length > 0
      || this.selectedVehicleModels().length > 0
      || this.selectedRegions().length > 0
      || this.selectedBrands().length > 0
      || !!this.dateFrom()
      || !!this.dateTo();
  }

  advancedFilterCount(): number {
    return this.selectedSeverities().length
      + this.selectedVehicleModels().length
      + this.selectedRegions().length
      + this.selectedBrands().length
      + (this.dateFrom() ? 1 : 0)
      + (this.dateTo() ? 1 : 0);
  }

  toggleAdvancedFilters() {
    this.showAdvancedFilters.set(!this.showAdvancedFilters());
  }

  toggleSortDir() {
    this.sortDir.set(this.sortDir() === 'asc' ? 'desc' : 'asc');
  }

  // Severity filter
  showSeverityFilter(): boolean { return this.activeFilter() === 'severity'; }
  getFilteredSeverities(): string[] {
    const options = ['Blocker', 'Critical', 'Major', 'Minor', 'Trivial'];
    const fromData = this.testCases().map(tc => tc.severity).filter((s): s is string => !!s && s.trim() !== '');
    const merged = [...new Set([...options, ...fromData])];
    if (!this.severitySearchTerm.trim()) return merged;
    return merged.filter(s => s.toLowerCase().includes(this.severitySearchTerm.toLowerCase()));
  }
  toggleSeverity(s: string) {
    const cur = this.selectedSeverities();
    this.selectedSeverities.set(cur.includes(s) ? cur.filter(x => x !== s) : [...cur, s]);
  }
  isSeveritySelected(s: string) { return this.selectedSeverities().includes(s); }
  clearSeverities() { this.selectedSeverities.set([]); }

  // Vehicle Model filter
  showVehicleModelFilter(): boolean { return this.activeFilter() === 'vehicleModel'; }
  getUniqueVehicleModels(): string[] {
    const arr = this.testCases().map(tc => tc.vehicle_model).filter((v): v is string => !!v && v.trim() !== '');
    return [...new Set(arr)].sort();
  }
  getFilteredVehicleModels(): string[] {
    const all = this.getUniqueVehicleModels();
    if (!this.vehicleModelSearchTerm.trim()) return all;
    return all.filter(v => v.toLowerCase().includes(this.vehicleModelSearchTerm.toLowerCase()));
  }
  toggleVehicleModel(v: string) {
    const cur = this.selectedVehicleModels();
    this.selectedVehicleModels.set(cur.includes(v) ? cur.filter(x => x !== v) : [...cur, v]);
  }
  isVehicleModelSelected(v: string) { return this.selectedVehicleModels().includes(v); }
  clearVehicleModels() { this.selectedVehicleModels.set([]); }

  // Region filter
  showRegionFilter(): boolean { return this.activeFilter() === 'region'; }
  getUniqueRegions(): string[] {
    const arr = this.testCases().flatMap(tc => TestCaseService.mvArray(tc.region));
    return [...new Set(arr)].sort();
  }
  getFilteredRegions(): string[] {
    const all = this.getUniqueRegions();
    if (!this.regionSearchTerm.trim()) return all;
    return all.filter(r => r.toLowerCase().includes(this.regionSearchTerm.toLowerCase()));
  }
  toggleRegion(r: string) {
    const cur = this.selectedRegions();
    this.selectedRegions.set(cur.includes(r) ? cur.filter(x => x !== r) : [...cur, r]);
  }
  isRegionSelected(r: string) { return this.selectedRegions().includes(r); }
  clearRegions() { this.selectedRegions.set([]); }

  // Brand filter
  showBrandFilter(): boolean { return this.activeFilter() === 'brand'; }
  getUniqueBrands(): string[] {
    const arr = this.testCases().flatMap(tc => TestCaseService.mvArray(tc.brand));
    return [...new Set(arr)].sort();
  }
  getFilteredBrands(): string[] {
    const all = this.getUniqueBrands();
    if (!this.brandSearchTerm.trim()) return all;
    return all.filter(b => b.toLowerCase().includes(this.brandSearchTerm.toLowerCase()));
  }
  toggleBrand(b: string) {
    const cur = this.selectedBrands();
    this.selectedBrands.set(cur.includes(b) ? cur.filter(x => x !== b) : [...cur, b]);
  }
  isBrandSelected(b: string) { return this.selectedBrands().includes(b); }
  clearBrands() { this.selectedBrands.set([]); }

  // Screen ID filter methods
  getFilteredScreenIds(): string[] {
    const allScreenIds = this.getUniqueScreenIds();
    if (!this.screenIdSearchTerm.trim()) return allScreenIds;
    return allScreenIds.filter(s => s.toLowerCase().includes(this.screenIdSearchTerm.toLowerCase()));
  }

  getUniqueScreenIds(): string[] {
    const screenIds = this.testCases().flatMap(tc => TestCaseService.mvArray(tc.screen_id));
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
    const features = this.testCases().flatMap(tc => TestCaseService.mvArray(tc.feature));
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
    // Multi-value fields are rendered as comma-separated strings in the
    // legacy edit modal; the backend coerces them back into arrays on
    // submit. The new create / detail screens render proper multi-selects.
    this.testCaseForm.patchValue({
      test_case_id: testCase.test_case_id,
      title: testCase.title || '',
      description: testCase.description || '',
      vehicle_model: testCase.vehicle_model || '',
      severity: testCase.severity || '',
      feature: TestCaseService.mvDisplay(testCase.feature),
      priority: testCase.priority || '',
      test_type: testCase.test_type || '',
      region: TestCaseService.mvDisplay(testCase.region),
      test_objective: testCase.test_objective || '',
      preconditions: testCase.preconditions || '',
      procedure: testCase.procedure || '',
      expected_behavior: testCase.expected_behavior || '',
      associated_requirement_id: TestCaseService.mvDisplay(testCase.associated_requirement_id),
      screen_id: TestCaseService.mvDisplay(testCase.screen_id),
      reference_document: TestCaseService.mvDisplay(testCase.reference_document),
      dr_applicable_screens: testCase.dr_applicable_screens || '',
      dr_id: testCase.dr_id || '',
      brand: TestCaseService.mvDisplay(testCase.brand),
      vehicle_variant: TestCaseService.mvDisplay(testCase.vehicle_variant),
      vehicle_specification: testCase.vehicle_specification || '',
      vehicle_mode: TestCaseService.mvDisplay((testCase as any).vehicle_mode),
      env_dependency: TestCaseService.mvDisplay(testCase.env_dependency),
      requirement_type: testCase.requirement_type || '',
      regulation: testCase.regulation || '',
      testsuite_type: TestCaseService.mvDisplay(testCase.testsuite_type)
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
          vehicle_mode: formData.vehicle_mode,
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
        vehicle_mode: formData.vehicle_mode,
        env_dependency: formData.env_dependency,
        requirement_type: formData.requirement_type,
        regulation: formData.regulation,
        testsuite_type: formData.testsuite_type
      };

      this.testCaseService.createTestCase(createData).subscribe({
        next: () => {
          this.closeModal();
          // Service pushes the new row through testCases$ so the list refreshes.
          this.isSubmitting.set(false);
        },
        error: (err) => {
          this.error.set(err?.message || 'Failed to create test case');
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

  /**
   * Pencil click in the row/grid action column. Opens the detail page with
   * `?edit=1` so the detail component can immediately flip into edit mode
   * instead of forcing a second click on the in-page Edit toggle.
   */
  navigateToDetailEdit(id: string | number) {
    this.router.navigate(['/test-cases', id], { queryParams: { edit: 1 } });
  }

  goToPage(page: number | '…') {
    if (page === '…') return;
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

  private markFormGroupTouched() {
    Object.keys(this.testCaseForm.controls).forEach(key => {
      const control = this.testCaseForm.get(key);
      control?.markAsTouched();
    });
  }
}
