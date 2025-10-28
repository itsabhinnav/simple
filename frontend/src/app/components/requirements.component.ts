import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { RequirementService } from '../services/requirement.service';

export interface Requirement {
  id?: number;
  requirement_id: string;
  title: string;
  description?: string;
  requirement_type?: string;
  given?: string;
  when_action?: string;
  then_result?: string;
  priority: string;
  status: string;
  assignee?: string;
  tags?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface RequirementCreateRequest {
  requirement_id: string;
  title: string;
  description?: string;
  given?: string;
  when?: string;
  then?: string;
  priority: string;
  status: string;
  assignee?: string;
  tags?: string;
}

export interface RequirementUpdateRequest {
  title?: string;
  description?: string;
  given?: string;
  when?: string;
  then?: string;
  priority?: string;
  status?: string;
  assignee?: string;
  tags?: string;
}

@Component({
  selector: 'app-requirements',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule],
  templateUrl: './requirements.component.html',
  styleUrl: './requirements.component.scss'
})
export class RequirementsComponent implements OnInit {
  private requirementService = inject(RequirementService);
  private formBuilder = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  requirements = signal<Requirement[]>([]);
  isLoading = signal(false);
  error = signal<string | null>(null);
  searchTerm = '';
  selectedStatus = signal<string>('all');
  selectedPriority = signal<string>('all');
  selectedAssignee = signal<string>('all');

  showModal = signal(false);
  isEditMode = signal(false);
  isSubmitting = signal(false);
  currentView = signal<'grid' | 'table' | 'browse'>('grid');
  
  requirementToEdit = signal<Requirement | null>(null);
  requirementForm: FormGroup;

  constructor() {
    this.requirementForm = this.formBuilder.group({
      requirement_id: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(100)]],
      title: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(500)]],
      description: [''],
      given: [''],
      when_action: [''],
      then_result: [''],
      priority: ['P2', Validators.required],
      status: ['Draft', Validators.required],
      assignee: [''],
      tags: ['']
    });
  }

  ngOnInit() {
    this.loadRequirements();
    
    // Redirect to browse view when selected
    this.currentView.subscribe(view => {
      if (view === 'browse') {
        this.router.navigate(['/split-view']);
      }
    });
  }

  loadRequirements() {
    this.isLoading.set(true);
    this.error.set(null);
    
    this.requirementService.getRequirements().subscribe({
      next: (requirements) => {
        console.log('Loaded requirements:', requirements);
        this.requirements.set(requirements || []);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load requirements');
        this.isLoading.set(false);
        console.error('Error loading requirements:', err);
      }
    });
  }

  filteredRequirements(): Requirement[] {
    let filtered = this.requirements();

    // Filter by search term
    if (this.searchTerm.trim()) {
      const term = this.searchTerm.toLowerCase();
      filtered = filtered.filter(req =>
        req.title.toLowerCase().includes(term) ||
        req.requirement_id.toLowerCase().includes(term) ||
        (req.description && req.description.toLowerCase().includes(term))
      );
    }

    // Filter by status
    if (this.selectedStatus() !== 'all') {
      filtered = filtered.filter(req => req.status === this.selectedStatus());
    }

    // Filter by priority
    if (this.selectedPriority() !== 'all') {
      filtered = filtered.filter(req => req.priority === this.selectedPriority());
    }

    // Filter by assignee
    if (this.selectedAssignee() !== 'all') {
      filtered = filtered.filter(req => req.assignee === this.selectedAssignee());
    }

    return filtered;
  }

  openCreateModal() {
    this.isEditMode.set(false);
    this.requirementForm.reset({
      priority: 'P2',
      status: 'Draft'
    });
    this.showModal.set(true);
  }

  openEditModal(requirement: Requirement) {
    this.isEditMode.set(true);
    this.requirementToEdit.set(requirement);
    this.requirementForm.patchValue({
      title: requirement.title,
      description: requirement.description || '',
      given: requirement.given || '',
      when_action: requirement.when_action || '',
      then_result: requirement.then_result || '',
      priority: requirement.priority,
      status: requirement.status,
      assignee: requirement.assignee || '',
      tags: requirement.tags || ''
    });
    this.showModal.set(true);
  }

  closeModal() {
    this.showModal.set(false);
    this.requirementForm.reset();
    this.requirementToEdit.set(null);
  }

  onSubmit() {
    if (this.requirementForm.invalid) {
      this.markFormGroupTouched(this.requirementForm);
      return;
    }

    this.isSubmitting.set(true);

    if (this.isEditMode()) {
      const reqId = this.requirementToEdit()?.id;
      if (!reqId) {
        this.isSubmitting.set(false);
        return;
      }

      const updateData: RequirementUpdateRequest = this.requirementForm.value;
      this.requirementService.updateRequirement(reqId, updateData).subscribe({
        next: () => {
          this.closeModal();
          this.loadRequirements();
        },
        error: (err) => {
          this.error.set('Failed to update requirement');
          this.isSubmitting.set(false);
          console.error('Error updating requirement:', err);
        }
      });
    } else {
      const createData: RequirementCreateRequest = {
        ...this.requirementForm.value,
        when: this.requirementForm.value.when_action
      };
      this.requirementService.createRequirement(createData).subscribe({
        next: () => {
          this.closeModal();
          this.loadRequirements();
        },
        error: (err) => {
          this.error.set('Failed to create requirement');
          this.isSubmitting.set(false);
          console.error('Error creating requirement:', err);
        }
      });
    }
  }

  deleteRequirement(id: number) {
    if (!confirm('Are you sure you want to delete this requirement?')) {
      return;
    }

    this.requirementService.deleteRequirement(id).subscribe({
      next: () => {
        this.loadRequirements();
      },
      error: (err) => {
        this.error.set('Failed to delete requirement');
        console.error('Error deleting requirement:', err);
      }
    });
  }

  getStatusClass(status: string): string {
    const statusMap: { [key: string]: string } = {
      'Draft': 'status-draft',
      'Approved': 'status-active',
      'Implemented': 'status-progress',
      'Tested': 'status-review',
      'Closed': 'status-completed'
    };
    return statusMap[status] || 'status-default';
  }

  getPriorityClass(priority: string): string {
    const priorityMap: { [key: string]: string } = {
      'P4': 'priority-low',
      'P3': 'priority-medium',
      'P2': 'priority-high',
      'P1': 'priority-critical'
    };
    return priorityMap[priority] || 'priority-default';
  }

  getUniqueAssignees(): string[] {
    const assignees = this.requirements()
      .map(req => req.assignee)
      .filter((assignee): assignee is string => assignee !== undefined && assignee !== null && assignee.trim() !== '');
    return [...new Set(assignees)];
  }

  navigateToDetail(id: number | undefined) {
    if (!id) {
      console.error('Cannot navigate: requirement ID is undefined');
      return;
    }
    console.log('Navigating to requirement detail:', id);
    this.router.navigate(['/requirements', id]);
  }

  private markFormGroupTouched(formGroup: FormGroup) {
    Object.keys(formGroup.controls).forEach(key => {
      formGroup.get(key)?.markAsTouched();
    });
  }
}

