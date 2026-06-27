import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { RequirementService } from '../services/requirement.service';
import { IdGeneratorService } from '../services/id-generator.service';
import { SpecService, Spec } from '../services/spec.service';
import { RequirementCreateRequest } from './requirements.component';

@Component({
  selector: 'app-create-requirement',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './create-requirement.component.html',
  styleUrl: './create-requirement.component.scss'
})
export class CreateRequirementComponent implements OnInit {
  private requirementService = inject(RequirementService);
  private idGenerator = inject(IdGeneratorService);
  private specService = inject(SpecService);
  private formBuilder = inject(FormBuilder);
  private router = inject(Router);
  private location = inject(Location);

  isSubmitting = signal(false);
  requirementForm: FormGroup;
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  isGeneratingId = signal(false);
  availableSpecs = signal<Spec[]>([]);
  specProjectFilter = signal('');
  selectedSpecRowId = signal('');

  filteredSpecs = computed(() => {
    const project = this.specProjectFilter();
    return this.availableSpecs().filter(s => {
      if (!project) return true;
      if (project === 'Unassigned') return !s.project?.trim();
      return (s.project || '') === project;
    });
  });

  specProjects = computed(() => {
    const names = new Set<string>();
    for (const s of this.availableSpecs()) {
      if (s.project?.trim()) names.add(s.project.trim());
    }
    return Array.from(names).sort();
  });

  goBack() {
    this.location.back();
  }

  constructor() {
    this.requirementForm = this.formBuilder.group({
      requirement_id: ['', [Validators.required]],
      srs_id: [''],
      title: ['', [Validators.required]],
      description: [''],
      given: [''],
      when_action: [''],
      then_result: [''],
      priority: ['', [Validators.required]],
      status: ['Draft', [Validators.required]],
      requirement_type: [''],
      assignee: [''],
      tags: [''],
      feature: [''],
      region: [''],
      brand: [''],
      reference_spec_id: [''],
      reference_spec_version: [''],
      requirement_version: [''],
      verification_method: [''],
      linked_epic_jira_id: [''],
      linked_test_case_ids: [''],
      linked_design_ids: ['']
    });
  }

  ngOnInit() {
    this.specService.getSpecs().subscribe(list => this.availableSpecs.set(list));

    // Auto-generate requirement ID
    this.isGeneratingId.set(true);
    this.idGenerator.generateNextRequirementId().subscribe({
      next: (nextId) => {
        this.requirementForm.patchValue({ requirement_id: nextId });
        this.isGeneratingId.set(false);
      },
      error: (err) => {
        console.error('Error generating ID:', err);
        // Fallback to default ID
        this.requirementForm.patchValue({ requirement_id: 'REQ_0001' });
        this.isGeneratingId.set(false);
      }
    });
  }

  onSpecProjectFilterChange(project: string) {
    this.specProjectFilter.set(project);
    this.selectedSpecRowId.set('');
    this.requirementForm.patchValue({ reference_spec_id: '', reference_spec_version: '' });
  }

  onReferenceSpecVersionChange(specRowId: string) {
    this.selectedSpecRowId.set(specRowId);
    const spec = this.availableSpecs().find(s => String(s.id) === specRowId);
    this.requirementForm.patchValue({
      reference_spec_id: spec?.spec_id || '',
      reference_spec_version: spec?.version || ''
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
      srs_id: formValue.srs_id,
      title: formValue.title,
      description: formValue.description,
      given: formValue.given,
      when: formValue.when_action,
      then: formValue.then_result,
      priority: formValue.priority,
      status: formValue.status,
      assignee: formValue.assignee,
      tags: formValue.tags,
      feature: formValue.feature,
      region: formValue.region,
      brand: formValue.brand,
      reference_spec_id: formValue.reference_spec_id,
      reference_spec_version: formValue.reference_spec_version,
      requirement_version: formValue.requirement_version,
      verification_method: formValue.verification_method,
      linked_epic_jira_id: formValue.linked_epic_jira_id,
      linked_test_case_ids: formValue.linked_test_case_ids,
      linked_design_ids: formValue.linked_design_ids
    };

    console.log('Creating requirement with data:', createRequest);

    this.requirementService.createRequirement(createRequest).subscribe({
      next: (requirement) => {
        // Defensive: a falsy payload means the backend rejected the row even
        // though the HTTP layer didn't surface an error. Don't pretend the
        // requirement was created in that case.
        if (!requirement) {
          this.isSubmitting.set(false);
          this.errorMessage.set('Failed to create requirement. The server did not return the new record.');
          window.scrollTo({ top: 0, behavior: 'smooth' });
          return;
        }
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
