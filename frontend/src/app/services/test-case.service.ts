import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

export interface TestCase {
  id?: number;
  test_case_id: string;
  reference_document?: string;
  associated_requirement_id?: string;
  screen_id?: string;
  feature?: string;
  dr_applicable_screens?: string;
  dr_id?: string;
  test_objective?: string;
  preconditions?: string;
  procedure?: string;
  expected_behavior?: string;
  test_type?: string;
  region?: string;
  brand?: string;
  vehicle_variant?: string;
  vehicle_specification?: string;
  env_dependency?: string;
  requirement_type?: string;
  regulation?: string;
  priority?: string;
  testsuite_type?: string;
  created_at?: string;
  updated_at?: string;
  is_high_priority?: boolean;
  has_requirements?: boolean;
  test_complexity?: string;
}

export interface TestCaseCreateRequest {
  test_case_id: string;
  reference_document?: string;
  associated_requirement_id?: string;
  screen_id?: string;
  feature?: string;
  dr_applicable_screens?: string;
  dr_id?: string;
  test_objective?: string;
  preconditions?: string;
  procedure?: string;
  expected_behavior?: string;
  test_type?: string;
  region?: string;
  brand?: string;
  vehicle_variant?: string;
  vehicle_specification?: string;
  env_dependency?: string;
  requirement_type?: string;
  regulation?: string;
  priority?: string;
  testsuite_type?: string;
}

export interface TestCaseUpdateRequest {
  test_case_id?: string;
  reference_document?: string;
  associated_requirement_id?: string;
  screen_id?: string;
  feature?: string;
  dr_applicable_screens?: string;
  dr_id?: string;
  test_objective?: string;
  preconditions?: string;
  procedure?: string;
  expected_behavior?: string;
  test_type?: string;
  region?: string;
  brand?: string;
  vehicle_variant?: string;
  vehicle_specification?: string;
  env_dependency?: string;
  requirement_type?: string;
  regulation?: string;
  priority?: string;
  testsuite_type?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data?: T;
  count?: number;
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class TestCaseService {
  private http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:5000/api';
  
  private testCasesSubject = new BehaviorSubject<TestCase[]>([]);
  public testCases$ = this.testCasesSubject.asObservable();

  constructor() {
    this.loadTestCases();
  }

  /**
   * Load all test cases from the API
   */
  loadTestCases(): void {
    this.http.get<ApiResponse<TestCase[]>>(`${this.baseUrl}/test-cases/`)
      .pipe(
        map(response => response.data || []),
        catchError(() => of([]))
      )
      .subscribe(testCases => {
        this.testCasesSubject.next(testCases);
      });
  }

  /**
   * Get all test cases as Observable
   */
  getTestCases(): Observable<TestCase[]> {
    return this.http.get<ApiResponse<TestCase[]>>(`${this.baseUrl}/test-cases/`)
      .pipe(
        map(response => response.data || []),
        catchError(() => of([]))
      );
  }

  /**
   * Get test case by ID
   */
  getTestCaseById(id: string): Observable<TestCase | null> {
    return this.http.get<ApiResponse<TestCase>>(`${this.baseUrl}/test-cases/${id}`)
      .pipe(
        map(response => response.data || null),
        catchError(() => of(null))
      );
  }

  /**
   * Get test cases by feature
   */
  getTestCasesByFeature(feature: string): Observable<TestCase[]> {
    const params = new URLSearchParams();
    params.set('feature', feature);
    
    return this.http.get<ApiResponse<TestCase[]>>(`${this.baseUrl}/test-cases/feature?${params.toString()}`)
      .pipe(
        map(response => response.data || []),
        catchError(() => of([]))
      );
  }

  /**
   * Create a new test case
   */
  createTestCase(testCaseData: TestCaseCreateRequest): Observable<TestCase | null> {
    return this.http.post<ApiResponse<TestCase>>(`${this.baseUrl}/test-cases/`, testCaseData)
      .pipe(
        map(response => {
          if (response.success && response.data) {
            // Update local cache
            const currentTestCases = this.testCasesSubject.value;
            this.testCasesSubject.next([response.data, ...currentTestCases]);
            return response.data;
          }
          return null;
        }),
        catchError(error => {
          console.error('Error creating test case:', error);
          return of(null);
        })
      );
  }

  /**
   * Update an existing test case
   */
  updateTestCase(id: string, testCaseData: TestCaseUpdateRequest): Observable<TestCase | null> {
    return this.http.put<ApiResponse<TestCase>>(`${this.baseUrl}/test-cases/${id}`, testCaseData)
      .pipe(
        map(response => {
          if (response.success && response.data) {
            // Update local cache
            const currentTestCases = this.testCasesSubject.value;
            const updatedTestCases = currentTestCases.map(testCase => 
              testCase.test_case_id === id ? response.data! : testCase
            );
            this.testCasesSubject.next(updatedTestCases);
            return response.data;
          }
          return null;
        }),
        catchError(error => {
          console.error('Error updating test case:', error);
          return of(null);
        })
      );
  }

  /**
   * Delete a test case
   */
  deleteTestCase(id: string): Observable<boolean> {
    return this.http.delete<ApiResponse<any>>(`${this.baseUrl}/test-cases/${id}`)
      .pipe(
        map(response => {
          if (response.success) {
            // Update local cache
            const currentTestCases = this.testCasesSubject.value;
            const filteredTestCases = currentTestCases.filter(testCase => testCase.test_case_id !== id);
            this.testCasesSubject.next(filteredTestCases);
            return true;
          }
          return false;
        }),
        catchError(() => of(false))
      );
  }

  /**
   * Get current test cases from subject
   */
  getCurrentTestCases(): TestCase[] {
    return this.testCasesSubject.value;
  }

  /**
   * Validate test case ID format (XX_FEATURE_XXX1)
   */
  isValidTestCaseId(testCaseId: string): boolean {
    const pattern = /^[A-Z]{2}_[A-Z_]+_\d+$/;
    return pattern.test(testCaseId);
  }

  /**
   * Validate priority
   */
  isValidPriority(priority: string): boolean {
    return ['P1', 'P2', 'P3'].includes(priority);
  }

  /**
   * Validate test type
   */
  isValidTestType(testType: string): boolean {
    return ['Positive', 'Negative', 'Boundary', 'Performance'].includes(testType);
  }

  /**
   * Check if test case ID is available
   */
  isTestCaseIdAvailable(testCaseId: string, currentTestCaseId?: string): boolean {
    const currentTestCases = this.testCasesSubject.value;
    return !currentTestCases.some(testCase => 
      testCase.test_case_id === testCaseId && 
      testCase.test_case_id !== currentTestCaseId
    );
  }

  /**
   * Get unique features from current test cases
   */
  getUniqueFeatures(): string[] {
    const currentTestCases = this.testCasesSubject.value;
    const features = currentTestCases
      .map(testCase => testCase.feature)
      .filter((feature): feature is string => feature !== undefined && feature.trim() !== '')
      .filter((feature, index, array) => array.indexOf(feature) === index);
    
    return features.sort();
  }

  /**
   * Get unique priorities from current test cases
   */
  getUniquePriorities(): string[] {
    return ['P1', 'P2', 'P3'];
  }

  /**
   * Get unique test types from current test cases
   */
  getUniqueTestTypes(): string[] {
    return ['Positive', 'Negative', 'Boundary', 'Performance'];
  }
}
