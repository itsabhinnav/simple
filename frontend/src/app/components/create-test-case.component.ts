import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import {
  TestCaseService,
  TestCaseCreateRequest,
  TestCaseDropdowns,
} from '../services/test-case.service';
import { IdGeneratorService } from '../services/id-generator.service';

@Component({
  selector: 'app-create-test-case',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterModule],
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

  /** Dropdown options sourced from `config.yaml > test_case_dropdowns`. */
  dropdowns = signal<TestCaseDropdowns | null>(null);

  /** Selected values for each multi-select field. */
  selected = {
    feature: signal<string[]>([]),
    region: signal<string[]>([]),
    brand: signal<string[]>([]),
    vehicle_variant: signal<string[]>([]),
    vehicle_specification: signal<string[]>([]),
    env_dependency: signal<string[]>([]),
    testsuite_type: signal<string[]>([]),
    reference_document: signal<string[]>([]),
    associated_requirement_id: signal<string[]>([]),
    screen_id: signal<string[]>([]),
  };

  /** Free-text input value per multi-select field for "add tag" UX. */
  multiInput: Record<string, string> = {
    feature: '',
    region: '',
    brand: '',
    vehicle_variant: '',
    vehicle_specification: '',
    env_dependency: '',
    testsuite_type: '',
    reference_document: '',
    associated_requirement_id: '',
    screen_id: '',
  };

  goBack() {
    this.location.back();
  }

  constructor() {
    this.testCaseForm = this.formBuilder.group({
      test_case_id: ['', [Validators.required]],
      title: [''],
      priority: [''],
      test_type: [''],
      severity: [''],
      regulation: [''],
      dr_id: [''],
      requirement_type: [''],
      test_objective: [''],
      preconditions: [''],
      procedure: [''],
      expected_behavior: [''],
      vehicle_model: [''],
    });
  }

  ngOnInit() {
    this.isGeneratingId.set(true);
    this.idGenerator.generateNextTestCaseId().subscribe({
      next: (nextId) => {
        this.testCaseForm.patchValue({ test_case_id: nextId });
        this.isGeneratingId.set(false);
      },
      error: (err) => {
        console.error('Error generating ID:', err);
        this.testCaseForm.patchValue({ test_case_id: 'TC_0001' });
        this.isGeneratingId.set(false);
      }
    });

    this.testCaseService.getDropdowns().subscribe({
      next: (data) => this.dropdowns.set(data),
      error: (err) => console.error('Failed to load dropdowns', err),
    });
  }

  // ---- multi-select chip helpers --------------------------------------
  /** Templates pass field names as strings, so type-erase to a Record lookup. */
  private get selectedMap(): Record<string, ReturnType<typeof signal<string[]>>> {
    return this.selected as unknown as Record<string, ReturnType<typeof signal<string[]>>>;
  }

  selectedValues(field: string): string[] {
    return this.selectedMap[field]?.() ?? [];
  }

  toggleMulti(field: string, value: string) {
    const sig = this.selectedMap[field];
    if (!sig) return;
    const current = sig();
    sig.set(current.includes(value) ? current.filter(v => v !== value) : [...current, value]);
  }

  isMultiSelected(field: string, value: string): boolean {
    return this.selectedValues(field).includes(value);
  }

  /** Add a free-text tag (for fields with no curated dropdown list). */
  addCustomTag(field: string, event?: Event) {
    if (event) event.preventDefault();
    const raw = (this.multiInput[field] || '').trim();
    if (!raw) return;
    const sig = this.selectedMap[field];
    if (!sig) return;
    const current = sig();
    if (!current.includes(raw)) {
      sig.set([...current, raw]);
    }
    this.multiInput[field] = '';
  }

  removeMulti(field: string, value: string) {
    const sig = this.selectedMap[field];
    if (!sig) return;
    sig.set(sig().filter(v => v !== value));
  }

  // ---- presentation helpers -------------------------------------------
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
      'Abnormal': 'status-progress'
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
      vehicle_model: formValue.vehicle_model,
      severity: formValue.severity,
      priority: formValue.priority,
      test_type: formValue.test_type,
      regulation: formValue.regulation,
      dr_id: formValue.dr_id,
      requirement_type: formValue.requirement_type,
      test_objective: formValue.test_objective,
      preconditions: formValue.preconditions,
      procedure: formValue.procedure,
      expected_behavior: formValue.expected_behavior,

      feature: this.selected.feature(),
      region: this.selected.region(),
      brand: this.selected.brand(),
      vehicle_variant: this.selected.vehicle_variant(),
      vehicle_specification: this.selected.vehicle_specification(),
      env_dependency: this.selected.env_dependency(),
      testsuite_type: this.selected.testsuite_type(),
      reference_document: this.selected.reference_document(),
      associated_requirement_id: this.selected.associated_requirement_id(),
      screen_id: this.selected.screen_id(),
    };

    this.testCaseService.createTestCase(createRequest).subscribe({
      next: (testCase) => {
        if (!testCase) {
          this.isSubmitting.set(false);
          this.errorMessage.set('Failed to create test case. The server did not return the new record.');
          window.scrollTo({ top: 0, behavior: 'smooth' });
          return;
        }
        this.isSubmitting.set(false);
        this.successMessage.set('Test case created successfully!');
        setTimeout(() => {
          this.router.navigate(['/test-cases']);
        }, 1500);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const errorMsg = err?.error?.message || err?.error?.error || err?.message || 'Failed to create test case. Please check the console for details.';
        this.errorMessage.set(errorMsg);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }
}
