import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { TestCaseService, TestCase } from '../services/test-case.service';

@Component({
  selector: 'app-test-case-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './test-case-detail.component.html',
  styleUrl: './test-case-detail.component.scss'
})
export class TestCaseDetailComponent implements OnInit {
  private testCaseService = inject(TestCaseService);
  private route = inject(ActivatedRoute);

  testCase = signal<TestCase | null>(null);
  isLoading = signal(false);
  error = signal<string | null>(null);
  testCaseId = signal<string | null>(null);

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      // Backend expects test_case_id (string), not numeric id
      this.testCaseId.set(id);
      this.loadTestCase(id);
    }
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
      'P4': 'priority-low',
      'P3': 'priority-medium',
      'P2': 'priority-high',
      'P1': 'priority-critical'
    };
    return priorityMap[priority] || 'priority-default';
  }

  deleteTestCase() {
    if (!this.testCaseId() || !confirm('Are you sure you want to delete this test case?')) {
      return;
    }

    this.testCaseService.deleteTestCase(String(this.testCaseId()!)).subscribe({
      next: () => {
        window.history.back();
      },
      error: (err) => {
        this.error.set('Failed to delete test case');
        console.error('Error deleting test case:', err);
      }
    });
  }
}

