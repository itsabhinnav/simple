import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { RequirementService } from '../services/requirement.service';
import { SplitViewComponent } from './split-view.component';

export interface Requirement {
  id?: number;
  requirement_id: string;
  srs_id?: string;
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
  feature?: string;
  region?: string;
  brand?: string;
  reference_spec_id?: string;
  reference_spec_version?: string;
  requirement_version?: string;
  verification_method?: string;
  linked_epic_jira_id?: string;
  linked_test_case_ids?: string;
  linked_design_ids?: string;
  linked_spec_id?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface RequirementCreateRequest {
  requirement_id: string;
  srs_id?: string;
  title: string;
  description?: string;
  given?: string;
  when?: string;
  then?: string;
  priority: string;
  status: string;
  assignee?: string;
  tags?: string;
  feature?: string;
  region?: string;
  brand?: string;
  reference_spec_id?: string;
  reference_spec_version?: string;
  requirement_version?: string;
  verification_method?: string;
  linked_epic_jira_id?: string;
  linked_test_case_ids?: string;
  linked_design_ids?: string;
  linked_spec_id?: string;
}

export interface RequirementUpdateRequest {
  title?: string;
  srs_id?: string;
  description?: string;
  given?: string;
  when?: string;
  then?: string;
  priority?: string;
  status?: string;
  assignee?: string;
  tags?: string;
  feature?: string;
  region?: string;
  brand?: string;
  reference_spec_id?: string;
  reference_spec_version?: string;
  requirement_version?: string;
  verification_method?: string;
  linked_epic_jira_id?: string;
  linked_test_case_ids?: string;
  linked_design_ids?: string;
  linked_spec_id?: string;
}

@Component({
  selector: 'app-requirements',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule, SplitViewComponent],
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
  searchTerm = signal<string>('');
  selectedStatus = signal<string>('all');
  selectedPriority = signal<string>('all');
  selectedAssignee = signal<string>('all');
  selectedType = signal<string>('all');
  selectedTags = signal<string[]>([]);
  dateFrom = signal<string>('');
  dateTo = signal<string>('');
  hasDescription = signal<'all' | 'with' | 'without'>('all');
  sortBy = signal<'updated_at' | 'created_at' | 'priority' | 'status' | 'requirement_id' | 'title'>('updated_at');
  sortDir = signal<'asc' | 'desc'>('desc');
  showAdvancedFilters = signal<boolean>(false);

  showModal = signal(false);
  isEditMode = signal(false);
  isSubmitting = signal(false);
  currentView = signal<'grid' | 'table' | 'browse'>('table');
  
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

    const term = this.searchTerm().trim().toLowerCase();
    if (term) {
      filtered = filtered.filter(req =>
        req.title.toLowerCase().includes(term) ||
        req.requirement_id.toLowerCase().includes(term) ||
        (req.description?.toLowerCase().includes(term) ?? false) ||
        (req.assignee?.toLowerCase().includes(term) ?? false) ||
        (req.tags?.toLowerCase().includes(term) ?? false) ||
        (req.given?.toLowerCase().includes(term) ?? false) ||
        (req.when_action?.toLowerCase().includes(term) ?? false) ||
        (req.then_result?.toLowerCase().includes(term) ?? false)
      );
    }

    if (this.selectedStatus() !== 'all') {
      filtered = filtered.filter(req => req.status === this.selectedStatus());
    }

    if (this.selectedPriority() !== 'all') {
      filtered = filtered.filter(req => req.priority === this.selectedPriority());
    }

    if (this.selectedAssignee() !== 'all') {
      const sel = this.selectedAssignee();
      filtered = sel === '__unassigned__'
        ? filtered.filter(req => !req.assignee || req.assignee.trim() === '')
        : filtered.filter(req => req.assignee === sel);
    }

    if (this.selectedType() !== 'all') {
      filtered = filtered.filter(req => (req.requirement_type || 'Functional') === this.selectedType());
    }

    const tagFilter = this.selectedTags();
    if (tagFilter.length > 0) {
      filtered = filtered.filter(req => {
        const reqTags = this.parseTags(req.tags);
        return tagFilter.every(t => reqTags.includes(t));
      });
    }

    const from = this.dateFrom();
    const to = this.dateTo();
    if (from || to) {
      const fromTs = from ? new Date(from).getTime() : -Infinity;
      const toTs = to ? new Date(to).getTime() + 86399999 : Infinity;
      filtered = filtered.filter(req => {
        if (!req.created_at) return false;
        const ts = new Date(req.created_at).getTime();
        return ts >= fromTs && ts <= toTs;
      });
    }

    if (this.hasDescription() === 'with') {
      filtered = filtered.filter(req => !!req.description?.trim());
    } else if (this.hasDescription() === 'without') {
      filtered = filtered.filter(req => !req.description?.trim());
    }

    const sortBy = this.sortBy();
    const dir = this.sortDir() === 'asc' ? 1 : -1;
    const priorityOrder: Record<string, number> = { P1: 1, P2: 2, P3: 3, P4: 4 };
    const statusOrder: Record<string, number> = { Draft: 1, Approved: 2, Implemented: 3, Tested: 4, Closed: 5 };
    filtered = [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'priority':
          cmp = (priorityOrder[a.priority] ?? 99) - (priorityOrder[b.priority] ?? 99);
          break;
        case 'status':
          cmp = (statusOrder[a.status] ?? 99) - (statusOrder[b.status] ?? 99);
          break;
        case 'requirement_id':
          cmp = a.requirement_id.localeCompare(b.requirement_id, undefined, { numeric: true });
          break;
        case 'title':
          cmp = a.title.localeCompare(b.title);
          break;
        case 'created_at':
          cmp = new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
          break;
        case 'updated_at':
        default:
          cmp = new Date(a.updated_at || a.created_at || 0).getTime() - new Date(b.updated_at || b.created_at || 0).getTime();
      }
      return cmp * dir;
    });

    return filtered;
  }

  private parseTags(tags: string | undefined | null): string[] {
    if (!tags) return [];
    return tags.split(',').map(t => t.trim()).filter(t => t.length > 0);
  }

  getUniqueTags(): string[] {
    const all = this.requirements().flatMap(req => this.parseTags(req.tags));
    return [...new Set(all)].sort((a, b) => a.localeCompare(b));
  }

  getUniqueTypes(): string[] {
    const types = this.requirements()
      .map(req => req.requirement_type)
      .filter((t): t is string => !!t && t.trim() !== '');
    return [...new Set(types)].sort();
  }

  toggleTag(tag: string) {
    const current = this.selectedTags();
    this.selectedTags.set(
      current.includes(tag) ? current.filter(t => t !== tag) : [...current, tag]
    );
  }

  isTagSelected(tag: string): boolean {
    return this.selectedTags().includes(tag);
  }

  toggleSortDir() {
    this.sortDir.set(this.sortDir() === 'asc' ? 'desc' : 'asc');
  }

  toggleAdvancedFilters() {
    this.showAdvancedFilters.set(!this.showAdvancedFilters());
  }

  activeFilterCount(): number {
    let count = 0;
    if (this.searchTerm().trim()) count++;
    if (this.selectedStatus() !== 'all') count++;
    if (this.selectedPriority() !== 'all') count++;
    if (this.selectedAssignee() !== 'all') count++;
    if (this.selectedType() !== 'all') count++;
    count += this.selectedTags().length;
    if (this.dateFrom()) count++;
    if (this.dateTo()) count++;
    if (this.hasDescription() !== 'all') count++;
    return count;
  }

  hasActiveFilters(): boolean {
    return this.activeFilterCount() > 0;
  }

  clearAllFilters() {
    this.searchTerm.set('');
    this.selectedStatus.set('all');
    this.selectedPriority.set('all');
    this.selectedAssignee.set('all');
    this.selectedType.set('all');
    this.selectedTags.set([]);
    this.dateFrom.set('');
    this.dateTo.set('');
    this.hasDescription.set('all');
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

      const raw = this.requirementForm.value;
      const updateData: RequirementUpdateRequest = {
        ...raw,
        when: raw.when_action,
        then: raw.then_result
      };
      delete (updateData as any).when_action;
      delete (updateData as any).then_result;

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
      const rawCreate = this.requirementForm.value;
      const createData: RequirementCreateRequest = {
        ...rawCreate,
        when: rawCreate.when_action,
        then: rawCreate.then_result
      };
      delete (createData as any).when_action;
      delete (createData as any).then_result;
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
    return [...new Set(assignees)].sort((a, b) => a.localeCompare(b));
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

