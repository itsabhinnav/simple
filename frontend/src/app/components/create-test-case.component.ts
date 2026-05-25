import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { TestCaseService, TestCaseCreateRequest } from '../services/test-case.service';
import { IdGeneratorService } from '../services/id-generator.service';

@Component({
  selector: 'app-create-test-case',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './create-test-case.component.html',
  styleUrl: './create-test-case.component.scss'
})
export class CreateTestCaseComponent implements OnInit {
  private testCaseService = inject(TestCaseService);
  private idGenerator = inject(IdGeneratorService);
  private formBuilder = inject(FormBuilder);
  private router = inject(Router);
  private location = inject(Location);

  isSubmitting = signal(false);
  testCaseForm: FormGroup;
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  isGeneratingId = signal(false);

  goBack() {
    this.location.back();
  }

  constructor() {
    this.testCaseForm = this.formBuilder.group({
      test_case_id: ['', [Validators.required]],
      title: [''],
      description: [''],
      vehicle_model: [''],
      severity: [''],
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
      requirement_type: [''],
      brand: [''],
      reference_document: ['']
    });
  }

  ngOnInit() {
    // Auto-generate test case ID
    this.isGeneratingId.set(true);
    this.idGenerator.generateNextTestCaseId().subscribe({
      next: (nextId) => {
        this.testCaseForm.patchValue({ test_case_id: nextId });
        this.isGeneratingId.set(false);
      },
      error: (err) => {
        console.error('Error generating ID:', err);
        // Fallback to default ID
        this.testCaseForm.patchValue({ test_case_id: 'TC_0001' });
        this.isGeneratingId.set(false);
      }
    });
  }

  getPriorityClass(priority: string): string {
    const priorityMap: { [key: string]: string } = {
      'P4': 'priority-low',
      'P3': 'priority-low',
      'P2': 'priority-medium',
      'P1': 'priority-high'
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
      title: formValue.title,
      description: formValue.description,
      vehicle_model: formValue.vehicle_model,
      severity: formValue.severity,
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
        // Defensive: only treat this as success if the backend actually
        // returned a persisted row. Previously the service swallowed HTTP
        // errors into `null` and this block flashed "created successfully"
        // for rows that were never inserted.
        if (!testCase) {
          this.isSubmitting.set(false);
          this.errorMessage.set('Failed to create test case. The server did not return the new record.');
          window.scrollTo({ top: 0, behavior: 'smooth' });
          return;
        }
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

        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }
}
