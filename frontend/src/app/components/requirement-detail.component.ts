import { Component, OnInit, inject, signal, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { RequirementService, Requirement } from '../services/requirement.service';
import { TestCaseService, TestCase } from '../services/test-case.service';
import { DesignTicketService, DesignTicket } from '../services/design-ticket.service';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';

@Component({
  selector: 'app-requirement-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './requirement-detail.component.html',
  styleUrl: './requirement-detail.component.scss'
})
export class RequirementDetailComponent implements OnInit, OnDestroy {
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);
  private designTicketService = inject(DesignTicketService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  requirement = signal<Requirement | null>(null);
  linkedTestCases = signal<TestCase[]>([]);
  linkedDesigns = signal<DesignTicket[]>([]);
  isLoading = signal(false);
  isLoadingTestCases = signal(false);
  isLoadingDesigns = signal(false);
  error = signal<string | null>(null);
  requirementId = signal<number | null>(null);
  isSaving = signal(false);
  saveStatus = signal<'idle' | 'saving' | 'saved' | 'error'>('idle');
  editingField = signal<string | null>(null);

  private saveSubject = new Subject<{ field: string; value: any }>();
  private saveSubscription?: Subscription;

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.requirementId.set(+id);
      this.loadRequirement(+id);
    }

    // Set up auto-save with debouncing
    this.saveSubscription = this.saveSubject.pipe(
      debounceTime(1000), // Wait 1 second after user stops typing
      distinctUntilChanged((a, b) => a.field === b.field && a.value === b.value)
    ).subscribe(({ field, value }) => {
      this.saveField(field, value);
    });
  }

  ngOnDestroy() {
    this.saveSubscription?.unsubscribe();
  }

  loadRequirement(id: number) {
    this.isLoading.set(true);
    this.error.set(null);

    this.requirementService.getRequirementById(id).subscribe({
      next: (requirement) => {
        if (requirement) {
          this.requirement.set(requirement);
          this.loadLinkedTestCases(requirement.requirement_id);
          this.loadLinkedDesigns(requirement.requirement_id);
        } else {
          this.error.set('Requirement not found');
        }
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load requirement');
        this.isLoading.set(false);
        console.error('Error loading requirement:', err);
      }
    });
  }

  loadLinkedTestCases(requirementId: string) {
    this.isLoadingTestCases.set(true);
    
    this.testCaseService.getTestCases().subscribe({
      next: (testCases) => {
        // Filter test cases that are linked to this requirement
        const linked = testCases.filter(tc => 
          tc.associated_requirement_id === requirementId
        );
        this.linkedTestCases.set(linked);
        this.isLoadingTestCases.set(false);
      },
      error: (err) => {
        console.error('Error loading linked test cases:', err);
        this.linkedTestCases.set([]);
        this.isLoadingTestCases.set(false);
      }
    });
  }

  loadLinkedDesigns(requirementId: string) {
    this.isLoadingDesigns.set(true);
    
    this.designTicketService.getDesignTickets().subscribe({
      next: (designs) => {
        // Filter designs that are linked to this requirement
        const linked = designs.filter(design => 
          design.linked_requirement_id === requirementId
        );
        this.linkedDesigns.set(linked);
        this.isLoadingDesigns.set(false);
      },
      error: (err) => {
        console.error('Error loading linked designs:', err);
        this.linkedDesigns.set([]);
        this.isLoadingDesigns.set(false);
      }
    });
  }

  navigateToTestCase(testCaseId: string) {
    this.router.navigate(['/test-cases', testCaseId]);
  }

  navigateToDesign(designTicketId: string) {
    this.router.navigate(['/design-tickets', designTicketId]);
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

  goBack() {
    if (typeof window !== 'undefined') {
      window.history.back();
    }
  }

  deleteRequirement() {
    if (!this.requirementId() || !confirm('Are you sure you want to delete this requirement?')) {
      return;
    }

    this.requirementService.deleteRequirement(this.requirementId()!).subscribe({
      next: () => {
        if (typeof window !== 'undefined') {
          window.history.back();
        }
      },
      error: (err) => {
        this.error.set('Failed to delete requirement');
        console.error('Error deleting requirement:', err);
      }
    });
  }

  startEdit(field: string) {
    this.editingField.set(field);
    setTimeout(() => {
      if (typeof document === 'undefined') return;
      const el = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(
        `[data-edit-field="${field}"]`
      );
      if (!el) return;
      el.focus();
      if (el.tagName === 'TEXTAREA') {
        const len = el.value.length;
        el.setSelectionRange(len, len);
      } else if ('select' in el && typeof (el as HTMLInputElement).select === 'function') {
        (el as HTMLInputElement).select();
      }
    }, 0);
  }

  stopEdit() {
    this.editingField.set(null);
  }

  isEditing(field: string): boolean {
    return this.editingField() === field;
  }

  onEditKeydown(event: KeyboardEvent, isMultiline: boolean = false) {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.stopEdit();
    } else if (event.key === 'Enter' && !isMultiline && !event.shiftKey) {
      event.preventDefault();
      this.stopEdit();
    }
  }

  onFieldChange(field: string, value: any) {
    if (!this.requirement()) return;
    
    // Update local signal immediately for responsive UI
    const current = this.requirement()!;
    this.requirement.set({ ...current, [field]: value });
    
    // Queue save operation
    this.saveSubject.next({ field, value });
    
    // Show saving status
    this.saveStatus.set('saving');
  }

  private saveField(field: string, value: any) {
    if (!this.requirementId() || !this.requirement()) return;

    this.isSaving.set(true);
    this.saveStatus.set('saving');

    const updateData: any = {};
    
    // Map frontend field names to backend API field names
    if (field === 'when_action') {
      updateData.when = value;
    } else if (field === 'then_result') {
      updateData.then = value;
    } else {
      updateData[field] = value;
    }

    this.requirementService.updateRequirement(this.requirementId()!, updateData).subscribe({
      next: (updatedRequirement) => {
        if (updatedRequirement) {
          // Update the requirement signal with fresh data from server
          this.requirement.set({ ...this.requirement()!, ...updatedRequirement });
          this.saveStatus.set('saved');
          
          // Clear saved status after 2 seconds
          setTimeout(() => {
            if (this.saveStatus() === 'saved') {
              this.saveStatus.set('idle');
            }
          }, 2000);
        }
        this.isSaving.set(false);
      },
      error: (err) => {
        console.error('Error saving field:', err);
        this.saveStatus.set('error');
        this.error.set(`Failed to save ${field}`);
        this.isSaving.set(false);
        
        // Reload requirement to get server state
        this.loadRequirement(this.requirementId()!);
        
        // Clear error status after 3 seconds
        setTimeout(() => {
          if (this.saveStatus() === 'error') {
            this.saveStatus.set('idle');
          }
        }, 3000);
      }
    });
  }
}


