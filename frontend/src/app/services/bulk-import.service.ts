import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { API_URL } from '../app-settings';
import type { ImportTarget } from './parsing.service';

/**
 * Generic deterministic bulk-import client. Talks to the per-resource
 * `/api/<resource>/import*` endpoints (`specifications`, `requirements`,
 * `design_tickets`, `test_cases`) — these all use the shared
 * `BulkImportService` on the backend so the same shape is returned for
 * every target.
 *
 * Used by the Smart Import wizard for the actual DB write phase. The
 * deterministic flow is intentionally kept authoritative for ID
 * uniqueness, defaults, and required-field enforcement; the new
 * `/api/parsing/*` engine only contributes AI-driven enrichment.
 */

export type BulkImportDuplicateStrategy = 'skip' | 'replace';

export interface BulkImportSheetPreview {
  sheet: string;
  target: string | null;
  row_count_estimate: number;
  raw_headers: string[];
  suggested_mapping: { [rawHeader: string]: string | null };
  known_fields: string[];
  id_field: string | null;
  required: string[];
  sample_rows: Array<Array<string | null>>;
}

export interface BulkImportPreview {
  file: string;
  sheets: BulkImportSheetPreview[];
}

export interface BulkImportSheetResult {
  sheet: string;
  target: string;
  created: number;
  updated?: number;
  skipped: number;
  failed: number;
  errors: Array<{ row?: number; id?: string; error: string }>;
}

export interface BulkImportFileResult {
  file: string;
  created: number;
  updated?: number;
  skipped: number;
  failed: number;
  sheets: BulkImportSheetResult[];
  errors: Array<{ sheet?: string; row?: number; id?: string; error: string }>;
}

export interface BulkImportResult {
  files: BulkImportFileResult[];
  totals: { created: number; updated?: number; skipped: number; failed: number };
}

export interface BulkImportFieldsResponse {
  target: string;
  id_field: string;
  required: string[];
  fields: string[];
}

interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}

const TARGET_PATHS: Record<ImportTarget, string> = {
  specifications: 'specs',
  requirements: 'requirements',
  design_tickets: 'design-tickets',
  test_cases: 'test-cases',
};

@Injectable({ providedIn: 'root' })
export class BulkImportService {
  private http = inject(HttpClient);

  private endpoint(target: ImportTarget): string {
    return `${API_URL}/${TARGET_PATHS[target]}`;
  }

  /** Canonical fields for a target — used by the mapping UI dropdowns. */
  getImportFields(target: ImportTarget): Observable<BulkImportFieldsResponse> {
    return this.http
      .get<ApiResponse<BulkImportFieldsResponse>>(`${this.endpoint(target)}/import/fields`)
      .pipe(
        map((res) => {
          if (!res.success || !res.data) {
            throw new Error(res.message || res.error || 'Failed to load fields');
          }
          return res.data;
        }),
      );
  }

  /** Per-sheet preview without inserting anything. */
  preview(target: ImportTarget, file: File, sampleRows = 5): Observable<BulkImportPreview> {
    const form = new FormData();
    form.append('file', file);
    form.append('sample_rows', String(sampleRows));
    return this.http
      .post<ApiResponse<BulkImportPreview>>(`${this.endpoint(target)}/import/preview`, form)
      .pipe(
        map((res) => {
          if (!res.success || !res.data) {
            throw new Error(res.message || res.error || 'Preview failed');
          }
          return res.data;
        }),
      );
  }

  /** Bulk import. Mapping is optional — unmapped headers fall back to auto-detect. */
  import(
    target: ImportTarget,
    files: File[],
    mapping?: { [rawHeader: string]: string },
    duplicateStrategy: BulkImportDuplicateStrategy = 'skip',
  ): Observable<BulkImportResult> {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    if (mapping && Object.keys(mapping).length > 0) {
      form.append('mapping', JSON.stringify(mapping));
    }
    form.append('duplicate_strategy', duplicateStrategy);
    return this.http
      .post<ApiResponse<BulkImportResult>>(`${this.endpoint(target)}/import`, form)
      .pipe(
        map((res) => {
          if (!res.data) {
            throw new Error(res.message || res.error || 'Bulk import failed');
          }
          return res.data;
        }),
      );
  }

  /** Human-friendly path for breadcrumbs / "View XYZ" CTAs. */
  routePath(target: ImportTarget): string {
    return `/${TARGET_PATHS[target]}`;
  }

  /** Pretty label per target (used in wizard headings). */
  label(target: ImportTarget): { singular: string; plural: string } {
    switch (target) {
      case 'specifications':
        return { singular: 'specification', plural: 'specifications' };
      case 'requirements':
        return { singular: 'requirement', plural: 'requirements' };
      case 'design_tickets':
        return { singular: 'design ticket', plural: 'design tickets' };
      case 'test_cases':
        return { singular: 'test case', plural: 'test cases' };
    }
  }
}
