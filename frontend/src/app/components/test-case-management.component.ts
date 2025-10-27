import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { TestCaseService, TestCase, TestCaseCreateRequest, TestCaseUpdateRequest } from '../services/test-case.service';

@Component({
  selector: 'app-test-case-management',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule],
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
        <button 
          class="add-btn" 
          routerLink="/test-cases/create"
          [disabled]="isLoading()">
          <i class="icon-plus"></i>
          Add New Test Case
        </button>
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

      <!-- Test Cases Table -->
      <div *ngIf="!isLoading() && !error()" class="table-container">
        <div class="table-header">
          <h3>Test Cases ({{ testCases().length }})</h3>
          <div class="search-box">
            <input 
              type="text" 
              placeholder="Search test cases..." 
              [(ngModel)]="searchTerm"
              class="search-input">
          </div>
        </div>

        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Test Case ID</th>
                <th>Feature</th>
                <th>Priority</th>
                <th>Test Type</th>
                <th>Complexity</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let testCase of filteredTestCases()">
                <td>{{ testCase.test_case_id }}</td>
                <td>{{ testCase.feature || 'N/A' }}</td>
                <td>
                  <span class="priority-badge" [class]="'priority-' + (testCase.priority || 'P3')">
                    {{ testCase.priority || 'P3' }}
                  </span>
                </td>
                <td>{{ testCase.test_type || 'N/A' }}</td>
                <td>
                  <span class="complexity-badge" [class]="testCase.test_complexity?.toLowerCase()">
                    {{ testCase.test_complexity || 'Low' }}
                  </span>
                </td>
                <td>
                  <span class="status-badge" [class]="testCase.has_requirements ? 'has-requirements' : 'no-requirements'">
                    {{ testCase.has_requirements ? 'Has Requirements' : 'No Requirements' }}
                  </span>
                </td>
                <td class="actions">
                  <button 
                    class="btn-edit" 
                    (click)="openEditModal(testCase)"
                    title="Edit Test Case">
                    <i class="icon-edit"></i>
                  </button>
                  <button 
                    class="btn-delete" 
                    (click)="confirmDelete(testCase)"
                    title="Delete Test Case">
                    <i class="icon-delete"></i>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Empty State -->
        <div *ngIf="filteredTestCases().length === 0" class="empty-state">
          <i class="icon-empty"></i>
          <h3>No Test Cases Found</h3>
          <p *ngIf="searchTerm">No test cases match your search criteria.</p>
          <p *ngIf="!searchTerm">No test cases available. Create your first test case!</p>
        </div>
      </div>

      <!-- Create/Edit Modal -->
      <div *ngIf="showModal()" class="modal-overlay" (click)="closeModal()">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <h2>{{ isEditMode() ? 'Edit Test Case' : 'Create New Test Case' }}</h2>
            <button class="close-btn" (click)="closeModal()">
              <i class="icon-close"></i>
            </button>
          </div>

          <form [formGroup]="testCaseForm" (ngSubmit)="onSubmit()" class="modal-body">
            <div class="form-group">
              <label for="testCaseId">Test Case ID *</label>
              <input 
                type="text" 
                id="testCaseId"
                formControlName="test_case_id"
                class="form-input"
                placeholder="e.g., TC_FEATURE_001"
                [class.error]="testCaseForm.get('test_case_id')?.invalid && testCaseForm.get('test_case_id')?.touched">
              <div *ngIf="testCaseForm.get('test_case_id')?.invalid && testCaseForm.get('test_case_id')?.touched" class="error-message">
                <span *ngIf="testCaseForm.get('test_case_id')?.errors?.['required']">Test Case ID is required</span>
                <span *ngIf="testCaseForm.get('test_case_id')?.errors?.['pattern']">Format: XX_FEATURE_XXX1 (e.g., TC_LOGIN_001)</span>
                <span *ngIf="testCaseForm.get('test_case_id')?.errors?.['testCaseIdExists']">Test Case ID already exists</span>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="feature">Feature</label>
                <input 
                  type="text" 
                  id="feature"
                  formControlName="feature"
                  class="form-input"
                  placeholder="e.g., Login, Dashboard">
              </div>
              <div class="form-group">
                <label for="priority">Priority</label>
                <select 
                  id="priority"
                  formControlName="priority"
                  class="form-select">
                  <option value="">Select Priority</option>
                  <option value="P1">P1 - High</option>
                  <option value="P2">P2 - Medium</option>
                  <option value="P3">P3 - Low</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="testType">Test Type</label>
                <select 
                  id="testType"
                  formControlName="test_type"
                  class="form-select">
                  <option value="">Select Test Type</option>
                  <option value="Positive">Positive</option>
                  <option value="Negative">Negative</option>
                  <option value="Boundary">Boundary</option>
                  <option value="Performance">Performance</option>
                </select>
              </div>
              <div class="form-group">
                <label for="region">Region</label>
                <input 
                  type="text" 
                  id="region"
                  formControlName="region"
                  class="form-input"
                  placeholder="e.g., US, EU, APAC">
              </div>
            </div>

            <div class="form-group">
              <label for="testObjective">Test Objective</label>
              <textarea 
                id="testObjective"
                formControlName="test_objective"
                class="form-textarea"
                rows="3"
                placeholder="Describe what this test case is designed to verify..."></textarea>
            </div>

            <div class="form-group">
              <label for="preconditions">Preconditions</label>
              <textarea 
                id="preconditions"
                formControlName="preconditions"
                class="form-textarea"
                rows="3"
                placeholder="List any prerequisites or setup requirements..."></textarea>
            </div>

            <div class="form-group">
              <label for="procedure">Test Procedure</label>
              <textarea 
                id="procedure"
                formControlName="procedure"
                class="form-textarea"
                rows="4"
                placeholder="Step-by-step instructions to execute the test..."></textarea>
            </div>

            <div class="form-group">
              <label for="expectedBehavior">Expected Behavior</label>
              <textarea 
                id="expectedBehavior"
                formControlName="expected_behavior"
                class="form-textarea"
                rows="3"
                placeholder="Describe the expected outcome..."></textarea>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="associatedRequirementId">Associated Requirement ID</label>
                <input 
                  type="text" 
                  id="associatedRequirementId"
                  formControlName="associated_requirement_id"
                  class="form-input"
                  placeholder="e.g., REQ_001">
              </div>
              <div class="form-group">
                <label for="screenId">Screen ID</label>
                <input 
                  type="text" 
                  id="screenId"
                  formControlName="screen_id"
                  class="form-input"
                  placeholder="e.g., SCR_001">
              </div>
            </div>

            <div class="form-actions">
              <button 
                type="button" 
                class="btn-cancel" 
                (click)="closeModal()">
                Cancel
              </button>
              <button 
                type="submit" 
                class="btn-submit"
                [disabled]="testCaseForm.invalid || isSubmitting()">
                <span *ngIf="isSubmitting()" class="spinner-small"></span>
                {{ isEditMode() ? 'Update Test Case' : 'Create Test Case' }}
              </button>
            </div>
          </form>
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
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    .management-header {
      background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
      color: white;
      padding: 20px;
      border-radius: 12px;
      margin-bottom: 30px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
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
      color: rgba(255, 255, 255, 0.8);
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 5px;
      transition: color 0.2s;
    }

    .breadcrumb-link:hover {
      color: white;
    }

    .breadcrumb-separator {
      color: rgba(255, 255, 255, 0.6);
    }

    .breadcrumb-current {
      color: white;
      font-weight: 500;
    }

    .page-title {
      margin: 0;
      font-size: 2rem;
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
      background: rgba(255, 255, 255, 0.2);
      color: white;
      border: 1px solid rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }

    .add-btn:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.3);
    }

    .add-btn:disabled {
      background: rgba(255, 255, 255, 0.1);
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
      border-top: 4px solid #4caf50;
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

    .actions {
      display: flex;
      gap: 8px;
    }

    .btn-edit, .btn-delete {
      padding: 6px 8px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.2s;
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

    .retry-btn {
      background: #4caf50;
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
      margin-top: 15px;
    }

    .retry-btn:hover {
      background: #388e3c;
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
      background: #4caf50;
      color: white;
    }

    .btn-submit:hover:not(:disabled) {
      background: #388e3c;
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
  `]
})
export class TestCaseManagementComponent implements OnInit {
  private testCaseService = inject(TestCaseService);
  private formBuilder = inject(FormBuilder);
  private route = inject(ActivatedRoute);

  // Signals for reactive state management
  testCases = signal<TestCase[]>([]);
  isLoading = signal(false);
  error = signal<string | null>(null);
  showModal = signal(false);
  isEditMode = signal(false);
  isSubmitting = signal(false);
  showDeleteModal = signal(false);
  isDeleting = signal(false);
  testCaseToDelete = signal<TestCase | null>(null);
  currentEditingTestCase = signal<TestCase | null>(null);
  searchTerm = '';

  testCaseForm: FormGroup;

  constructor() {
    this.testCaseForm = this.formBuilder.group({
      test_case_id: ['', [
        Validators.required,
        Validators.pattern(/^[A-Z]{2}_[A-Z_]+_\d+$/)
      ]],
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
  }

  ngOnInit() {
    // Subscribe to the service's test cases observable for real-time updates
    this.testCaseService.testCases$.subscribe(testCases => {
      this.testCases.set(testCases);
    });
    
    // Load initial data
    this.loadTestCases();
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

  filteredTestCases(): TestCase[] {
    if (!this.searchTerm.trim()) {
      return this.testCases();
    }
    
    const term = this.searchTerm.toLowerCase();
    return this.testCases().filter(testCase => 
      testCase.test_case_id.toLowerCase().includes(term) ||
      (testCase.feature && testCase.feature.toLowerCase().includes(term)) ||
      (testCase.test_objective && testCase.test_objective.toLowerCase().includes(term)) ||
      (testCase.procedure && testCase.procedure.toLowerCase().includes(term))
    );
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

  private markFormGroupTouched() {
    Object.keys(this.testCaseForm.controls).forEach(key => {
      const control = this.testCaseForm.get(key);
      control?.markAsTouched();
    });
  }
}
