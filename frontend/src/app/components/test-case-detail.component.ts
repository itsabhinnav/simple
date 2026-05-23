import { Component, OnInit, inject, signal, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { TestCaseService, TestCase } from '../services/test-case.service';
import { RequirementService } from '../services/requirement.service';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';

@Component({
  selector: 'app-test-case-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './test-case-detail.component.html',
  styleUrl: './test-case-detail.component.scss'
})
export class TestCaseDetailComponent implements OnInit, OnDestroy {
  private testCaseService = inject(TestCaseService);
  private requirementService = inject(RequirementService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  testCase = signal<TestCase | null>(null);
  isLoading = signal(false);
  error = signal<string | null>(null);
  testCaseId = signal<string | null>(null);
  isSaving = signal(false);
  saveStatus = signal<'idle' | 'saving' | 'saved' | 'error'>('idle');
  
  private saveSubject = new Subject<{ field: string; value: any }>();
  private saveSubscription?: Subscription;

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      // Backend expects test_case_id (string), not numeric id
      this.testCaseId.set(id);
      this.loadTestCase(id);
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

  loadTestCase(id: string) {
    this.isLoading.set(true);
    this.error.set(null);

    this.testCaseService.getTestCaseById(id).subscribe({
      next: (testCase) => {
        if (testCase) {
          this.testCase.set(testCase);
        } else {
          this.error.set('Test case not found');
        }
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load test case');
        this.isLoading.set(false);
        console.error('Error loading test case:', err);
      }
    });
  }

  getStatusClass(status: string): string {
    const statusMap: { [key: string]: string } = {
      'Pass': 'status-pass',
      'Fail': 'status-fail',
      'Blocked': 'status-blocked',
      'Not Run': 'status-not-run',
      'In Progress': 'status-progress'
    };
    return statusMap[status] || 'status-default';
  }

  getPriorityClass(priority: string): string {
    const priorityMap: { [key: string]: string } = {
      'P3': 'priority-low',
      'P2': 'priority-medium',
      'P1': 'priority-high',
    };
    return priorityMap[priority] || 'priority-default';
  }

  getTypeClass(testType: string): string {
    const typeMap: { [key: string]: string } = {
      'Positive': 'status-pass',
      'Negative': 'status-fail',
      'Boundary': 'status-blocked',
      'Performance': 'status-progress'
    };
    return typeMap[testType] || 'status-default';
  }

  goBack() {
    if (typeof window !== 'undefined') {
      window.history.back();
    }
  }

  deleteTestCase() {
    if (!this.testCaseId() || !confirm('Are you sure you want to delete this test case?')) {
      return;
    }

    this.testCaseService.deleteTestCase(String(this.testCaseId()!)).subscribe({
      next: () => {
        if (typeof window !== 'undefined') {
          window.history.back();
        }
      },
      error: (err) => {
        this.error.set('Failed to delete test case');
        console.error('Error deleting test case:', err);
      }
    });
  }

  navigateToRequirement(requirementId: string) {
    if (!requirementId) {
      console.error('Cannot navigate: requirement ID is empty');
      return;
    }

    // Get the requirement by requirement_id to find its numeric id
    this.requirementService.getRequirementByRequirementId(requirementId).subscribe({
      next: (requirement) => {
        if (requirement && requirement.id) {
          console.log('Navigating to requirement detail:', requirement.id);
          this.router.navigate(['/requirements', requirement.id]);
        } else {
          console.error('Requirement not found:', requirementId);
          alert(`Requirement ${requirementId} not found`);
        }
      },
      error: (err) => {
        console.error('Error loading requirement:', err);
        alert(`Failed to load requirement ${requirementId}`);
      }
    });
  }

  onFieldChange(field: string, value: any) {
    if (!this.testCase()) return;
    
    // Update local signal immediately for responsive UI
    const current = this.testCase()!;
    this.testCase.set({ ...current, [field]: value });
    
    // Queue save operation
    this.saveSubject.next({ field, value });
    
    // Show saving status
    this.saveStatus.set('saving');
  }

  private saveField(field: string, value: any) {
    if (!this.testCaseId() || !this.testCase()) return;

    this.isSaving.set(true);
    this.saveStatus.set('saving');

    const updateData: any = {};
    updateData[field] = value;

    this.testCaseService.updateTestCase(this.testCaseId()!, updateData).subscribe({
      next: (updatedTestCase) => {
        if (updatedTestCase) {
          // Update the test case signal with fresh data from server
          this.testCase.set({ ...this.testCase()!, ...updatedTestCase });
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
        
        // Reload test case to get server state
        this.loadTestCase(this.testCaseId()!);
        
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

