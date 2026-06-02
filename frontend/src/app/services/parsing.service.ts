import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';
import { API_URL } from '../app-settings';

/**
 * Wrapper for the new robust hybrid parsing engine exposed at
 * `/api/parsing/*`. The Smart Import wizard uses this alongside the
 * existing deterministic bulk-import flow (`*.service.ts.previewImport`,
 * `*.service.ts.import*`) — deterministic remains authoritative for the
 * actual DB writes; this service provides AI-driven enrichment.
 */

export type ImportTarget =
  | 'specifications'
  | 'requirements'
  | 'design_tickets'
  | 'test_cases';

export interface ParseProvidersResponse {
  default: string | null;
  providers: string[];
}

export interface ParseTargetCatalog {
  [target: string]: {
    id_field: string;
    required: string[];
    fields: string[];
  };
}

export interface SmartPreviewSheet {
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

export interface SmartPreviewDeterministic {
  file: string;
  sheets: SmartPreviewSheet[];
  error?: string;
}

export interface SmartPreviewAi {
  requested: boolean;
  skipped: boolean;
  error?: string;
  artifact_kind?: string;
  file_type?: string;
  warnings?: string[];
  deterministic_summary?: any;
  vlm?: any;
  conflicts?: any[];
  structured_payload?: any;
}

export interface SmartPreviewResponse {
  file: string;
  target?: string | null;
  deterministic: SmartPreviewDeterministic;
  ai: SmartPreviewAi;
  providers: ParseProvidersResponse;
  supported_targets: ImportTarget[];
}

export interface ParseSubmission {
  task_id: string;
  status_url: string;
  result_url: string;
  submitted_at?: string;
  target_hint?: string;
}

export interface ParseTaskStatus {
  task_id: string;
  status: string;
  progress?: string;
  info: any;
  result?: any;
  submitted_at?: string;
}

interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}

export interface SmartPreviewOptions {
  target?: ImportTarget;
  provider?: string;
  sampleRows?: number;
  enableAi?: boolean;
  enableVisual?: boolean;
  enableVlm?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ParsingService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_URL}/parsing`;

  /**
   * Synchronous unified preview. Combines the deterministic header
   * detection with optional AI-driven artifact classification +
   * semantic overlays. Always best-effort: AI failures degrade to a
   * `skipped: true` payload rather than failing the whole call.
   */
  smartPreview(file: File, opts: SmartPreviewOptions = {}): Observable<SmartPreviewResponse> {
    const form = new FormData();
    form.append('file', file);
    if (opts.target) form.append('target', opts.target);
    if (opts.provider) form.append('provider', opts.provider);
    if (opts.sampleRows != null) form.append('sample_rows', String(opts.sampleRows));
    form.append('enable_ai', opts.enableAi ? 'true' : 'false');
    form.append('enable_visual', opts.enableVisual ? 'true' : 'false');
    form.append('enable_vlm', opts.enableVlm ? 'true' : 'false');
    return this.http.post<ApiResponse<SmartPreviewResponse>>(`${this.baseUrl}/smart-preview`, form).pipe(
      map((res) => {
        if (!res.success || !res.data) {
          throw new Error(res.message || res.error || 'Smart preview failed');
        }
        return res.data;
      }),
    );
  }

  /**
   * Submit a parse for the full hybrid pipeline. Returns either a sync
   * payload (when `mode='sync'`) or an async task descriptor with
   * `task_id` + `status_url` for polling.
   */
  parse(
    file: File,
    options: {
      mode?: 'async' | 'sync';
      provider?: string;
      target?: ImportTarget;
      enableVisual?: boolean;
      enableVlm?: boolean;
    } = {},
  ): Observable<ParseSubmission | any> {
    const form = new FormData();
    form.append('file', file);
    form.append('mode', options.mode || 'async');
    if (options.provider) form.append('provider', options.provider);
    if (options.target) form.append('target', options.target);
    if (options.enableVisual != null) form.append('enable_visual', String(options.enableVisual));
    if (options.enableVlm != null) form.append('enable_vlm', String(options.enableVlm));
    return this.http
      .post<ApiResponse<ParseSubmission | any>>(`${this.baseUrl}/parse`, form)
      .pipe(
        map((res) => {
          if (!res.success || !res.data) {
            throw new Error(res.message || res.error || 'Parse failed');
          }
          return res.data;
        }),
      );
  }

  getTaskStatus(taskId: string): Observable<ParseTaskStatus> {
    return this.http
      .get<ApiResponse<ParseTaskStatus>>(`${this.baseUrl}/tasks/${taskId}`)
      .pipe(map((res) => res.data as ParseTaskStatus));
  }

  getTaskResult(taskId: string): Observable<any | null> {
    return this.http
      .get<ApiResponse<any>>(`${this.baseUrl}/tasks/${taskId}/result`)
      .pipe(map((res) => res.data ?? null));
  }

  listProviders(): Observable<ParseProvidersResponse> {
    return this.http
      .get<ApiResponse<ParseProvidersResponse>>(`${this.baseUrl}/providers`)
      .pipe(
        map((res) => res.data || { default: null, providers: [] }),
        catchError(() => of({ default: null, providers: [] } as ParseProvidersResponse)),
      );
  }

  listTargets(): Observable<ParseTargetCatalog> {
    return this.http
      .get<ApiResponse<{ targets: ParseTargetCatalog }>>(`${this.baseUrl}/targets`)
      .pipe(
        map((res) => res.data?.targets || {}),
        catchError(() => of({} as ParseTargetCatalog)),
      );
  }
}
