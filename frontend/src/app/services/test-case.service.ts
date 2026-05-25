import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, throwError } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';
import { API_URL } from '../app-settings';

export interface TestCase {
  id?: number;
  test_case_id: string;
  title?: string;
  description?: string;
  vehicle_model?: string;
  severity?: string;
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
  title?: string;
  description?: string;
  vehicle_model?: string;
  severity?: string;
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
  title?: string;
  description?: string;
  vehicle_model?: string;
  severity?: string;
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

/**
 * Excel import — types returned by /api/test-cases/import/preview and /import.
 */
export interface TestCaseImportSheetPreview {
  sheet: string;
  target: string | null;
  row_count_estimate: number;
  raw_headers: string[];
  /** Map of raw header → backend's auto-detected canonical field (or null). */
  suggested_mapping: { [rawHeader: string]: string | null };
  known_fields: string[];
  id_field: string | null;
  required: string[];
  sample_rows: Array<Array<string | null>>;
}

export interface TestCaseImportPreview {
  file: string;
  sheets: TestCaseImportSheetPreview[];
}

export interface TestCaseImportSheetResult {
  sheet: string;
  target: string;
  created: number;
  /** Number of existing rows updated when duplicate_strategy = 'replace'. */
  updated?: number;
  skipped: number;
  failed: number;
  errors: Array<{ row?: number; id?: string; error: string }>;
}

export interface TestCaseImportFileResult {
  file: string;
  created: number;
  updated?: number;
  skipped: number;
  failed: number;
  sheets: TestCaseImportSheetResult[];
  errors: Array<{ sheet?: string; row?: number; id?: string; error: string }>;
}

export interface TestCaseImportResult {
  files: TestCaseImportFileResult[];
  totals: { created: number; updated?: number; skipped: number; failed: number };
}

/** What to do for rows whose ID is already in the DB. */
export type TestCaseImportDuplicateStrategy = 'skip' | 'replace';

export interface TestCaseImportFieldsResponse {
  target: string;
  id_field: string;
  required: string[];
  fields: string[];
}

@Injectable({
  providedIn: 'root'
})
export class TestCaseService {
  private http = inject(HttpClient);
  private readonly baseUrl = API_URL;
  
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
   * Create a new test case.
   *
   * Errors must propagate to the caller — silently returning `null` on backend
   * failure causes the standalone create page to flash a "created successfully"
   * banner for rows that were actually rejected (e.g. invalid test_case_id
   * format), which is what users were seeing.
   */
  createTestCase(testCaseData: TestCaseCreateRequest): Observable<TestCase> {
    return this.http.post<ApiResponse<TestCase>>(`${this.baseUrl}/test-cases/`, testCaseData)
      .pipe(
        map(response => {
          if (response.success && response.data) {
            const currentTestCases = this.testCasesSubject.value;
            this.testCasesSubject.next([response.data, ...currentTestCases]);
            return response.data;
          }
          throw new Error(response.message || response.error || 'Failed to create test case');
        }),
        catchError(error => {
          console.error('Error creating test case:', error);
          const msg = error?.error?.message || error?.error?.error || error?.message || 'Failed to create test case';
          return throwError(() => new Error(msg));
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
   * Excel preview: parse a single workbook and return detected headers,
   * auto-mapping suggestions, and sample rows so the user can confirm the
   * mapping before importing 10k+ rows. Does not insert anything.
   */
  previewImport(file: File, sampleRows: number = 5): Observable<TestCaseImportPreview> {
    const form = new FormData();
    form.append('file', file);
    form.append('sample_rows', String(sampleRows));
    return this.http
      .post<ApiResponse<TestCaseImportPreview>>(`${this.baseUrl}/test-cases/import/preview`, form)
      .pipe(
        map(response => {
          if (!response.success || !response.data) {
            throw new Error(response.message || response.error || 'Preview failed');
          }
          return response.data;
        })
      );
  }

  /**
   * Spreadsheet bulk-import. Pass one or more `.xlsx`, `.xlsm`, or `.csv`
   * files and an optional `mapping` of {rawHeader: canonicalField}.
   * Unmapped headers fall back to auto-detection.
   *
   * `duplicateStrategy` controls what happens when an incoming row's ID is
   * already present:
   *   - `'skip'`    (default) — leave the existing row alone
   *   - `'replace'` — UPDATE the existing row with the spreadsheet values
   *
   * Returns per-sheet/per-file counts (created / updated / skipped / failed).
   */
  importTestCases(
    files: File[],
    mapping?: { [rawHeader: string]: string },
    duplicateStrategy: TestCaseImportDuplicateStrategy = 'skip',
  ): Observable<TestCaseImportResult> {
    const form = new FormData();
    files.forEach(f => form.append('files', f));
    if (mapping && Object.keys(mapping).length > 0) {
      form.append('mapping', JSON.stringify(mapping));
    }
    form.append('duplicate_strategy', duplicateStrategy);
    return this.http
      .post<ApiResponse<TestCaseImportResult>>(`${this.baseUrl}/test-cases/import`, form)
      .pipe(
        map(response => {
          if (!response.data) {
            throw new Error(response.message || response.error || 'Bulk import failed');
          }
          // Refresh local cache after a successful import so the table
          // immediately reflects newly created OR updated rows.
          const t = response.data.totals;
          if ((t?.created || 0) > 0 || (t?.updated || 0) > 0) {
            this.loadTestCases();
          }
          return response.data;
        })
      );
  }

  /** Canonical fields for the test_cases target — used by the mapping UI dropdowns. */
  getImportFields(): Observable<TestCaseImportFieldsResponse> {
    return this.http
      .get<ApiResponse<TestCaseImportFieldsResponse>>(`${this.baseUrl}/test-cases/import/fields`)
      .pipe(
        map(response => {
          if (!response.success || !response.data) {
            throw new Error(response.message || response.error || 'Failed to load fields');
          }
          return response.data;
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
