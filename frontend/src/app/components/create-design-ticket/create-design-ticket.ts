import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { DesignTicketService, DesignTicketCreateRequest } from '../../services/design-ticket.service';

@Component({
  selector: 'app-create-design-ticket',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="create-page-container">
      <div class="page-header">
        <button class="back-btn" (click)="goBack()">
          ← Back
        </button>
        <h1>Create New Design Ticket</h1>
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
        <form [formGroup]="designTicketForm" (ngSubmit)="onSubmit()" class="create-form">
          <div class="form-section">
            <h2 class="section-title">Basic Information</h2>
            
            <div class="form-group">
              <label for="design_ticket_id">Design Ticket ID *</label>
              <input 
                type="text" 
                id="design_ticket_id"
                formControlName="design_ticket_id"
                class="form-input"
                placeholder="e.g., DT-001">
              <div *ngIf="designTicketForm.get('design_ticket_id')?.invalid && designTicketForm.get('design_ticket_id')?.touched" class="error-message">
                Design Ticket ID is required
              </div>
            </div>

            <div class="form-group">
              <label for="title">Title *</label>
              <input 
                type="text" 
                id="title"
                formControlName="title"
                class="form-input"
                placeholder="Enter design ticket title">
              <div *ngIf="designTicketForm.get('title')?.invalid && designTicketForm.get('title')?.touched" class="error-message">
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
                placeholder="Describe the design ticket..."></textarea>
            </div>
          </div>

          <div class="form-section">
            <h2 class="section-title">Design Details</h2>
            
            <div class="form-row">
              <div class="form-group">
                <label for="design_type">Design Type</label>
                <select 
                  id="design_type"
                  formControlName="design_type"
                  class="form-input">
                  <option value="">Select Design Type</option>
                  <option value="Sequence Diagram">Sequence Diagram</option>
                  <option value="Use Case Diagram">Use Case Diagram</option>
                  <option value="State Flow">State Flow</option>
                  <option value="Architecture Diagram">Architecture Diagram</option>
                  <option value="ER Diagram">ER Diagram</option>
                  <option value="Flowchart">Flowchart</option>
                  <option value="Wireframe">Wireframe</option>
                  <option value="Mockup">Mockup</option>
                </select>
              </div>

              <div class="form-group">
                <label for="diagram_type">Diagram Type</label>
                <input 
                  type="text" 
                  id="diagram_type"
                  formControlName="diagram_type"
                  class="form-input"
                  placeholder="Specific diagram type">
              </div>
            </div>

            <div class="form-group">
              <label for="image_url">Image URL</label>
              <input 
                type="text" 
                id="image_url"
                formControlName="image_url"
                class="form-input"
                placeholder="Path to uploaded image">
              <div class="field-hint">
                Images will be stored in /data/local/dev/images/
              </div>
            </div>

            <div class="form-group">
              <label for="requirement_id">Linked Requirement ID</label>
              <input 
                type="text" 
                id="requirement_id"
                formControlName="requirement_id"
                class="form-input"
                placeholder="e.g., REQ-001">
              <div class="field-hint">
                Optional: Link this design to a requirement
              </div>
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
                  <option value="P1">Critical (P1)</option>
                  <option value="P2">High (P2)</option>
                  <option value="P3">Medium (P3)</option>
                  <option value="P4">Low (P4)</option>
                </select>
                <div *ngIf="designTicketForm.get('priority')?.invalid && designTicketForm.get('priority')?.touched" class="error-message">
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
                  <option value="Review">Review</option>
                  <option value="Approved">Approved</option>
                  <option value="Archived">Archived</option>
                </select>
                <div *ngIf="designTicketForm.get('status')?.invalid && designTicketForm.get('status')?.touched" class="error-message">
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
                placeholder="e.g., ui, ux, frontend">
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
              [disabled]="designTicketForm.invalid || isSubmitting()">
              <span *ngIf="isSubmitting()" class="spinner"></span>
              {{ isSubmitting() ? 'Creating...' : 'Create Design Ticket' }}
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
    }

    .back-btn:hover {
      background: #e8eaed;
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
    }

    .form-section:not(:last-child) {
      border-bottom: 1px solid #e8eaed;
      padding-bottom: 32px;
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
    }

    .form-input:focus, .form-textarea:focus {
      outline: none;
      border-color: #1a73e8;
      box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.1);
    }

    .form-textarea {
      resize: vertical;
      min-height: 80px;
    }

    .field-hint {
      color: #5f6368;
      font-size: 12px;
      margin-top: 4px;
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
    }

    .btn-cancel:hover {
      background: #e8eaed;
    }

    .btn-submit {
      background: #1a73e8;
      color: white;
    }

    .btn-submit:hover:not(:disabled) {
      background: #1557b0;
    }

    .btn-submit:disabled {
      background: #bdbdbd;
      cursor: not-allowed;
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
export class CreateDesignTicket implements OnInit {
  private designTicketService = inject(DesignTicketService);
  private formBuilder = inject(FormBuilder);
  private router = inject(Router);
  private location = inject(Location);

  isSubmitting = signal(false);
  designTicketForm: FormGroup;
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  constructor() {
    this.designTicketForm = this.formBuilder.group({
      design_ticket_id: ['', [Validators.required]],
      title: ['', [Validators.required]],
      description: [''],
      design_type: [''],
      diagram_type: [''],
      image_url: [''],
      priority: ['P2', [Validators.required]],
      status: ['Draft', [Validators.required]],
      requirement_id: [''],
      assignee: [''],
      tags: ['']
    });
  }

  ngOnInit() {}

  goBack() {
    this.location.back();
  }

  onSubmit() {
    if (this.designTicketForm.invalid) {
      this.markFormGroupTouched(this.designTicketForm);
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    const data: DesignTicketCreateRequest = this.designTicketForm.value;

    this.designTicketService.createDesignTicket(data).subscribe({
      next: (result) => {
        this.isSubmitting.set(false);
        this.successMessage.set(`Design ticket ${data.design_ticket_id} created successfully!`);
        setTimeout(() => {
          this.router.navigate(['/design-tickets']);
        }, 1500);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const errorMsg = err.error?.message || err.message || 'Failed to create design ticket';
        this.errorMessage.set(errorMsg);
        console.error('Error creating design ticket:', err);
      }
    });
  }

  private markFormGroupTouched(formGroup: FormGroup) {
    Object.keys(formGroup.controls).forEach(key => {
      formGroup.get(key)?.markAsTouched();
    });
  }
}
