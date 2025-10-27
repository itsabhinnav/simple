import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { TestCaseService, TestCaseCreateRequest } from '../services/test-case.service';

@Component({
  selector: 'app-create-test-case',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="create-page-container">
      <div class="page-header">
        <button class="back-btn" routerLink="/">
          ← Back
        </button>
        <h1>Create New Test Case</h1>
      </div>

      <!-- Error Message -->
      <div *ngIf="errorMessage()" class="alert alert-error">
        <strong>Error:</strong> {{ errorMessage() }}
      </div>

      <!-- Success Message -->
      <div *ngIf="successMessage()" class="alert alert-success">
        <strong>Success:</strong> {{ successMessage() }}
      </div>

      <div class="form-container">
        <form [formGroup]="testCaseForm" (ngSubmit)="onSubmit()" class="create-form">
          <div class="form-section">
            <h2 class="section-title">Basic Information</h2>
            
            <div class="form-group">
              <label for="test_case_id">Test Case ID *</label>
              <input 
                type="text" 
                id="test_case_id"
                formControlName="test_case_id"
                class="form-input"
                placeholder="e.g., TC_FEATURE_001">
              <div *ngIf="testCaseForm.get('test_case_id')?.invalid && testCaseForm.get('test_case_id')?.touched" class="error-message">
                <span *ngIf="testCaseForm.get('test_case_id')?.errors?.['required']">Test Case ID is required</span>
                <span *ngIf="testCaseForm.get('test_case_id')?.errors?.['pattern']">Format: XX_FEATURE_XXX1 (e.g., TC_LOGIN_001)</span>
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
                  class="form-input">
                  <option value="">Select Priority</option>
                  <option value="P1">P1 - High</option>
                  <option value="P2">P2 - Medium</option>
                  <option value="P3">P3 - Low</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="test_type">Test Type</label>
                <select 
                  id="test_type"
                  formControlName="test_type"
                  class="form-input">
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
          </div>

          <div class="form-section">
            <h2 class="section-title">Test Details</h2>
            
            <div class="form-group">
              <label for="test_objective">Test Objective</label>
              <textarea 
                id="test_objective"
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
              <label for="expected_behavior">Expected Behavior</label>
              <textarea 
                id="expected_behavior"
                formControlName="expected_behavior"
                class="form-textarea"
                rows="3"
                placeholder="Describe the expected outcome..."></textarea>
            </div>
          </div>

          <div class="form-section">
            <h2 class="section-title">Additional Information</h2>
            
            <div class="form-row">
              <div class="form-group">
                <label for="associated_requirement_id">Associated Requirement ID</label>
                <input 
                  type="text" 
                  id="associated_requirement_id"
                  formControlName="associated_requirement_id"
                  class="form-input"
                  placeholder="e.g., REQ_001">
              </div>
              <div class="form-group">
                <label for="screen_id">Screen ID</label>
                <input 
                  type="text" 
                  id="screen_id"
                  formControlName="screen_id"
                  class="form-input"
                  placeholder="e.g., SCR_001">
              </div>
            </div>

            <div class="form-group">
              <label for="reference_document">Reference Document</label>
              <input 
                type="text" 
                id="reference_document"
                formControlName="reference_document"
                class="form-input"
                placeholder="Document reference">
            </div>
          </div>

          <div class="form-actions">
            <button 
              type="button" 
              class="btn-cancel" 
              routerLink="/">
              Cancel
            </button>
            <button 
              type="submit" 
              class="btn-submit"
              [disabled]="testCaseForm.invalid || isSubmitting()">
              <span *ngIf="isSubmitting()" class="spinner"></span>
              {{ isSubmitting() ? 'Creating...' : 'Create Test Case' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .create-page-container {
      max-width: 900px;
      margin: 0 auto;
      padding: 24px;
    }

    .page-header {
      margin-bottom: 32px;
    }

    .back-btn {
      padding: 8px 16px;
      background: #f5f5f5;
      border: 1px solid #dadce0;
      border-radius: 6px;
      color: #202124;
      text-decoration: none;
      display: inline-block;
      margin-bottom: 16px;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
      
      &:hover {
        background: #e8eaed;
      }
    }

    h1 {
      font-size: 28px;
      color: #202124;
      margin: 0;
    }

    .form-container {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 12px;
      padding: 32px;
    }

    .form-section {
      margin-bottom: 32px;
      
      &:not(:last-child) {
        border-bottom: 1px solid #e8eaed;
        padding-bottom: 32px;
      }
    }

    .section-title {
      font-size: 18px;
      color: #202124;
      margin-bottom: 20px;
      font-weight: 500;
    }

    .form-group {
      margin-bottom: 20px;
    }

    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }

    label {
      display: block;
      margin-bottom: 8px;
      font-weight: 500;
      color: #202124;
      font-size: 14px;
    }

    .form-input, .form-textarea {
      width: 100%;
      padding: 12px;
      border: 1px solid #dadce0;
      border-radius: 6px;
      font-size: 14px;
      transition: border-color 0.2s;
      font-family: inherit;
      
      &:focus {
        outline: none;
        border-color: #1a73e8;
        box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.1);
      }
    }

    .form-textarea {
      resize: vertical;
      min-height: 80px;
    }

    .error-message {
      color: #c62828;
      font-size: 12px;
      margin-top: 4px;
    }

    .form-actions {
      display: flex;
      gap: 12px;
      justify-content: flex-end;
      padding-top: 24px;
      margin-top: 24px;
      border-top: 1px solid #e8eaed;
    }

    .btn-cancel, .btn-submit {
      padding: 12px 24px;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .btn-cancel {
      background: #f5f5f5;
      color: #202124;
      
      &:hover {
        background: #e8eaed;
      }
    }

    .btn-submit {
      background: #1a73e8;
      color: white;
      
      &:hover:not(:disabled) {
        background: #1557b0;
      }
      
      &:disabled {
        background: #bdbdbd;
        cursor: not-allowed;
      }
    }

    .spinner {
      width: 16px;
      height: 16px;
      border: 2px solid transparent;
      border-top: 2px solid currentColor;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `]
})
export class CreateTestCaseComponent implements OnInit {
  private testCaseService = inject(TestCaseService);
  private formBuilder = inject(FormBuilder);
  private router = inject(Router);

  isSubmitting = signal(false);
  testCaseForm: FormGroup;
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  constructor() {
    this.testCaseForm = this.formBuilder.group({
      test_case_id: ['', [Validators.required, Validators.pattern(/^[A-Z]{2}_[A-Z_]+_\d+$/)]],
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
      reference_document: ['']
    });
  }

  ngOnInit() {}

  onSubmit() {
    if (this.testCaseForm.invalid) {
      this.errorMessage.set('Please fill in all required fields.');
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    
    const formValue = this.testCaseForm.value;
    const createRequest: TestCaseCreateRequest = {
      test_case_id: formValue.test_case_id,
      feature: formValue.feature,
      priority: formValue.priority,
      test_type: formValue.test_type,
      region: formValue.region,
      test_objective: formValue.test_objective,
      preconditions: formValue.preconditions,
      procedure: formValue.procedure,
      expected_behavior: formValue.expected_behavior,
      associated_requirement_id: formValue.associated_requirement_id,
      screen_id: formValue.screen_id,
      reference_document: formValue.reference_document
    };

    console.log('Creating test case with data:', createRequest);

    this.testCaseService.createTestCase(createRequest).subscribe({
      next: (testCase) => {
        console.log('Test case created successfully:', testCase);
        this.isSubmitting.set(false);
        this.successMessage.set('Test case created successfully!');
        setTimeout(() => {
          this.router.navigate(['/test-cases']);
        }, 1500);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        console.error('Error creating test case:', err);
        
        const errorMsg = err?.error?.message || err?.error?.error || err?.message || 'Failed to create test case. Please check the console for details.';
        this.errorMessage.set(errorMsg);
        
        // Scroll to top to show error
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }
}

