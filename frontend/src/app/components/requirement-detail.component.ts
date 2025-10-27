import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { RequirementService, Requirement } from '../services/requirement.service';
import { TestCaseService, TestCase } from '../services/test-case.service';

@Component({
  selector: 'app-requirement-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './requirement-detail.component.html',
  styleUrl: './requirement-detail.component.scss'
})
export class RequirementDetailComponent implements OnInit {
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  requirement = signal<Requirement | null>(null);
  linkedTestCases = signal<TestCase[]>([]);
  isLoading = signal(false);
  isLoadingTestCases = signal(false);
  error = signal<string | null>(null);
  requirementId = signal<number | null>(null);

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.requirementId.set(+id);
      this.loadRequirement(+id);
    }
  }

  loadRequirement(id: number) {
    this.isLoading.set(true);
    this.error.set(null);

    this.requirementService.getRequirementById(id).subscribe({
      next: (requirement) => {
        if (requirement) {
          this.requirement.set(requirement);
          this.loadLinkedTestCases(requirement.requirement_id);
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

  navigateToTestCase(testCaseId: string) {
    this.router.navigate(['/test-cases', testCaseId]);
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
}


