import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, throwError } from 'rxjs';
import { map, catchError, shareReplay, tap } from 'rxjs/operators';
import { of } from 'rxjs';
import { API_URL } from '../app-settings';

/**
 * Field names that store multiple values (persisted as JSON arrays
 * server-side). The dropdown configuration endpoint also returns this
 * list under `multi_value_fields` — keep the two in sync if you add a
 * new column.
 */
export const TEST_CASE_MULTI_VALUE_FIELDS = [
  'reference_document',
  'associated_requirement_id',
  'screen_id',
  'feature',
  'region',
  'brand',
  'vehicle_variant',
  'vehicle_mode',
  'env_dependency',
  'testsuite_type',
] as const;

export type TestCaseMultiValueField = typeof TEST_CASE_MULTI_VALUE_FIELDS[number];

/**
 * Multi-value fields are stored server-side as JSON arrays but legacy
 * code paths (and the bulk import service) still emit plain strings. The
 * union keeps both shapes valid; consumers should normalise via the
 * `TestCaseService.mvArray` / `mvDisplay` helpers below.
 */
export type MultiValue = string | string[] | undefined;

export interface TestCase {
  id?: number;
  test_case_id: string;
  title?: string;
  description?: string;
  vehicle_model?: string;
  severity?: string;

  reference_document?: MultiValue;
  associated_requirement_id?: MultiValue;
  screen_id?: MultiValue;
  feature?: MultiValue;
  region?: MultiValue;
  brand?: MultiValue;
  vehicle_variant?: MultiValue;
  vehicle_mode?: MultiValue;
  env_dependency?: MultiValue;
  testsuite_type?: MultiValue;

  dr_applicable_screens?: string;
  dr_id?: string;
  test_objective?: string;
  preconditions?: string;
  procedure?: string;
  expected_behavior?: string;
  test_type?: string;
  vehicle_specification?: string;
  requirement_type?: string;
  /** "Yes" / "No" — single-select dropdown driven by config.yaml. */
  regulation?: string;
  priority?: string;

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

  reference_document?: MultiValue;
  associated_requirement_id?: MultiValue;
  screen_id?: MultiValue;
  feature?: MultiValue;
  region?: MultiValue;
  brand?: MultiValue;
  vehicle_variant?: MultiValue;
  vehicle_mode?: MultiValue;
  env_dependency?: MultiValue;
  testsuite_type?: MultiValue;

  dr_applicable_screens?: string;
  dr_id?: string;
  test_objective?: string;
  preconditions?: string;
  procedure?: string;
  expected_behavior?: string;
  test_type?: string;
  vehicle_specification?: string;
  requirement_type?: string;
  regulation?: string;
  priority?: string;
}

export type TestCaseUpdateRequest = Partial<TestCaseCreateRequest>;

/**
 * Shape of GET /api/test-cases/dropdowns. Each option list is configurable
 * via `config.yaml > test_case_dropdowns`. `multi_value_fields` echoes
 * which fields the backend persists as JSON arrays so the UI can render
 * single vs. multi pickers from the same source.
 */
export interface TestCaseDropdowns {
  multi_value_fields: string[];
  feature: string[];
  test_type: string[];
  region: string[];
  brand: string[];
  vehicle_variant: string[];
  vehicle_mode: string[];
  env_dependency: string[];
  regulation: string[];
  priority: string[];
  testsuite_type: string[];
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
  /**
   * Coerce a multi-value field (array, CSV string, or scalar) into a
   * plain `string[]`. Empty / blank entries are dropped, so callers can
   * rely on `mvArray(...).length === 0` for the "no values" check.
   */
  static mvArray(value: MultiValue): string[] {
    if (value === null || value === undefined) {
      return [];
    }
    if (Array.isArray(value)) {
      return value
        .map(v => (v ?? '').toString().trim())
        .filter(v => v !== '');
    }
    const str = value.toString().trim();
    if (str === '') {
      return [];
    }
    if (str.startsWith('[') && str.endsWith(']')) {
      try {
        const parsed = JSON.parse(str);
        if (Array.isArray(parsed)) {
          return parsed
            .map(v => (v ?? '').toString().trim())
            .filter(v => v !== '');
        }
      } catch {
        /* fall through to CSV split */
      }
    }
    return str.split(',').map(s => s.trim()).filter(Boolean);
  }

  /** Join a multi-value field with `, ` for read-only display / search. */
  static mvDisplay(value: MultiValue, separator = ', '): string {
    return TestCaseService.mvArray(value).join(separator);
  }

  private http = inject(HttpClient);
  private readonly baseUrl = API_URL;
  
  private testCasesSubject = new BehaviorSubject<TestCase[]>([]);
  public testCases$ = this.testCasesSubject.asObservable();

  /** In-memory dropdown cache. Populated lazily by the first `getDropdowns()` call. */
  private dropdownsCache$: Observable<TestCaseDropdowns> | null = null;
  public readonly dropdowns = signal<TestCaseDropdowns | null>(null);

  constructor() {
    this.loadTestCases();
    // Warm the dropdown cache once on app boot so create / detail screens
    // never show empty selects.
    this.getDropdowns().subscribe({ error: () => { /* fail silently */ } });
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

  /**
   * Fetch dropdown / multi-select options sourced from `config.yaml`.
   * Cached for the lifetime of the service so create + detail screens
   * share a single network call.
   */
  getDropdowns(forceReload = false): Observable<TestCaseDropdowns> {
    if (forceReload) {
      this.dropdownsCache$ = null;
    }
    if (!this.dropdownsCache$) {
      this.dropdownsCache$ = this.http
        .get<ApiResponse<TestCaseDropdowns>>(`${this.baseUrl}/test-cases/dropdowns`)
        .pipe(
          map(response => {
            if (!response.success || !response.data) {
              throw new Error(response.message || response.error || 'Failed to load dropdowns');
            }
            return response.data;
          }),
          tap(data => this.dropdowns.set(data)),
          shareReplay({ bufferSize: 1, refCount: false }),
        );
    }
    return this.dropdownsCache$;
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
   * Validate priority against the configured dropdown values, falling
   * back to the historical hard-coded list if config has not loaded yet.
   */
  isValidPriority(priority: string): boolean {
    const configured = this.dropdowns()?.priority;
    return (configured && configured.length ? configured : ['P1', 'P2', 'P3', 'P4']).includes(priority);
  }

  isValidTestType(testType: string): boolean {
    const configured = this.dropdowns()?.test_type;
    return (configured && configured.length ? configured : ['Positive', 'Negative', 'Abnormal', 'Boundary']).includes(testType);
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
    // `feature` is multi-value (string | string[]); flatten via mvArray then dedupe.
    const features = this.testCasesSubject.value
      .flatMap(tc => TestCaseService.mvArray(tc.feature));
    return [...new Set(features)].sort();
  }

  /**
   * Get unique priorities from current test cases
   */
  getUniquePriorities(): string[] {
    return this.dropdowns()?.priority ?? ['P1', 'P2', 'P3', 'P4'];
  }

  getUniqueTestTypes(): string[] {
    return this.dropdowns()?.test_type ?? ['Positive', 'Negative', 'Abnormal', 'Boundary'];
  }
}
