import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { RequirementService } from '../services/requirement.service';
import { RequirementCreateRequest } from './requirements.component';

@Component({
  selector: 'app-create-requirement',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="create-page-container">
      <div class="page-header">
        <button class="back-btn" (click)="goBack()">
          ← Back
        </button>
        <h1>Create New Requirement</h1>
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
        <form [formGroup]="requirementForm" (ngSubmit)="onSubmit()" class="create-form">
          <div class="form-section">
            <h2 class="section-title">Basic Information</h2>
            
            <div class="form-group">
              <label for="requirement_id">Requirement ID *</label>
              <input 
                type="text" 
                id="requirement_id"
                formControlName="requirement_id"
                class="form-input"
                placeholder="e.g., REQ-001">
              <div *ngIf="requirementForm.get('requirement_id')?.invalid && requirementForm.get('requirement_id')?.touched" class="error-message">
                Requirement ID is required
              </div>
            </div>

            <div class="form-group">
              <label for="title">Title *</label>
              <input 
                type="text" 
                id="title"
                formControlName="title"
                class="form-input"
                placeholder="Enter requirement title">
              <div *ngIf="requirementForm.get('title')?.invalid && requirementForm.get('title')?.touched" class="error-message">
                Title is required
              </div>
            </div>

            <div class="form-group">
              <label for="description">Description</label>
              <textarea 
                id="description"
                formControlName="description"
                class="form-textarea"
                rows="4"
                placeholder="Describe the requirement..."></textarea>
            </div>
          </div>

          <div class="form-section">
            <h2 class="section-title">Acceptance Criteria (BDD Format)</h2>
            
            <div class="form-group">
              <label for="given">Given (Preconditions)</label>
              <textarea 
                id="given"
                formControlName="given"
                class="form-textarea"
                rows="2"
                placeholder="Preconditions or setup..."></textarea>
            </div>

            <div class="form-group">
              <label for="when_action">When (Action)</label>
              <textarea 
                id="when_action"
                formControlName="when_action"
                class="form-textarea"
                rows="2"
                placeholder="The action taken..."></textarea>
            </div>

            <div class="form-group">
              <label for="then_result">Then (Expected Result)</label>
              <textarea 
                id="then_result"
                formControlName="then_result"
                class="form-textarea"
                rows="2"
                placeholder="The expected outcome..."></textarea>
            </div>
          </div>

          <div class="form-section">
            <h2 class="section-title">Additional Information</h2>
            
            <div class="form-row">
              <div class="form-group">
                <label for="priority">Priority *</label>
                <select 
                  id="priority"
                  formControlName="priority"
                  class="form-input">
                  <option value="">Select Priority</option>
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
                <div *ngIf="requirementForm.get('priority')?.invalid && requirementForm.get('priority')?.touched" class="error-message">
                  Priority is required
                </div>
              </div>

              <div class="form-group">
                <label for="status">Status *</label>
                <select 
                  id="status"
                  formControlName="status"
                  class="form-input">
                  <option value="">Select Status</option>
                  <option value="Draft">Draft</option>
                  <option value="Active">Active</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Review">Review</option>
                  <option value="Completed">Completed</option>
                  <option value="Archived">Archived</option>
                </select>
                <div *ngIf="requirementForm.get('status')?.invalid && requirementForm.get('status')?.touched" class="error-message">
                  Status is required
                </div>
              </div>
            </div>

            <div class="form-group">
              <label for="assignee">Assignee</label>
              <input 
                type="text" 
                id="assignee"
                formControlName="assignee"
                class="form-input"
                placeholder="e.g., John Doe">
            </div>

            <div class="form-group">
              <label for="tags">Tags</label>
              <input 
                type="text" 
                id="tags"
                formControlName="tags"
                class="form-input"
                placeholder="e.g., feature, enhancement, bug">
            </div>
          </div>

          <div class="form-actions">
            <button 
              type="button" 
              class="btn-cancel" 
              (click)="goBack()">
              Cancel
            </button>
            <button 
              type="submit" 
              class="btn-submit"
              [disabled]="requirementForm.invalid || isSubmitting()">
              <span *ngIf="isSubmitting()" class="spinner"></span>
              {{ isSubmitting() ? 'Creating...' : 'Create Requirement' }}
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

    .alert {
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      animation: slideDown 0.3s ease-out;
    }

    .alert-error {
      background-color: #ffebee;
      border: 1px solid #e57373;
      color: #c62828;
    }

    .alert-success {
      background-color: #e8f5e9;
      border: 1px solid #81c784;
      color: #2e7d32;
    }

    .alert strong {
      font-weight: 600;
    }

    @keyframes slideDown {
      from {
        opacity: 0;
        transform: translateY(-10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
  `]
})
export class CreateRequirementComponent implements OnInit {
  private requirementService = inject(RequirementService);
  private formBuilder = inject(FormBuilder);
  private router = inject(Router);
  private location = inject(Location);

  isSubmitting = signal(false);
  requirementForm: FormGroup;
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  goBack() {
    this.location.back();
  }

  constructor() {
    this.requirementForm = this.formBuilder.group({
      requirement_id: ['', [Validators.required]],
      title: ['', [Validators.required]],
      description: [''],
      given: [''],
      when_action: [''],
      then_result: [''],
      priority: ['', [Validators.required]],
      status: ['Draft', [Validators.required]],
      assignee: [''],
      tags: ['']
    });
  }

  ngOnInit() {}

  onSubmit() {
    if (this.requirementForm.invalid) {
      this.errorMessage.set('Please fill in all required fields.');
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    
    const formValue = this.requirementForm.value;
    const createRequest: RequirementCreateRequest = {
      requirement_id: formValue.requirement_id,
      title: formValue.title,
      description: formValue.description,
      given: formValue.given,
      when: formValue.when_action,
      then: formValue.then_result,
      priority: formValue.priority,
      status: formValue.status,
      assignee: formValue.assignee,
      tags: formValue.tags
    };

    console.log('Creating requirement with data:', createRequest);

    this.requirementService.createRequirement(createRequest).subscribe({
      next: (requirement) => {
        console.log('Requirement created successfully:', requirement);
        this.isSubmitting.set(false);
        this.successMessage.set('Requirement created successfully!');
        setTimeout(() => {
          this.router.navigate(['/requirements']);
        }, 1500);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        console.error('Error creating requirement:', err);
        
        // Extract error message from various possible error formats
        let errorMsg = 'Failed to create requirement';
        
        if (err?.error) {
          // HTTP error response
          errorMsg = err.error.message || err.error.error || err.error;
        } else if (err?.message) {
          // JavaScript error
          errorMsg = err.message;
        } else if (typeof err === 'string') {
          errorMsg = err;
        } else {
          errorMsg = 'Unknown error occurred. Please check the console for details.';
        }
        
        this.errorMessage.set(errorMsg);
        
        // Scroll to top to show error
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }
}

