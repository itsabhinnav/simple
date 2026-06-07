import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { API_URL } from '../app-settings';

export interface AdminSettingsResponse {
  file_path: string | null;
  editable_sections: string[];
  read_only_sections: string[];
  sections: Record<string, any>;
}

export interface ImportTargetSchema {
  table: string;
  id_field: string;
  prefix: string;
  required: string[];
  fields: string[];
  default_required: string[];
  default_fields: string[];
}

export interface ImportSchemaResponse {
  targets: Record<string, ImportTargetSchema>;
  header_aliases: Record<string, string | null>;
}

export interface LlmProviderConfig {
  base_url?: string;
  model?: string;
  lite_model?: string;
  [key: string]: any;
}

export interface LlmConfigResponse {
  default: string;
  registered: string[];
  providers: Record<string, LlmProviderConfig>;
  api_keys: Record<string, { env: string; set: boolean }>;
  schema: Record<string, string[]>;
}

export interface LlmConfigUpdatePayload {
  default?: string;
  providers?: Record<string, LlmProviderConfig>;
}

export interface LlmTestResponse {
  success: boolean;
  message?: string;
  data?: { models?: string[]; configured_model?: string; env_var?: string; set?: boolean };
  error?: string;
}

export interface SchemaColumn {
  cid?: number;
  name: string;
  type: string;
  nullable: boolean;
  default: any;
  primary_key: boolean;
}

export interface SchemaIndex {
  name: string;
  unique: boolean;
  origin: string;
  columns: string[];
}

export interface SchemaTable {
  name: string;
  protected: boolean;
  row_count: number;
  columns: SchemaColumn[];
  indexes: SchemaIndex[];
  foreign_keys: any[];
}

export interface SchemaTableSummary {
  name: string;
  column_count: number;
  row_count: number;
  protected: boolean;
}

export interface SchemaMigrationRow {
  id: number;
  applied_at: string;
  applied_by: string | null;
  operation: string;
  table_name: string | null;
  column_name: string | null;
  details: string | null;
  succeeded: number;
  error: string | null;
  backup_path: string | null;
}

export interface SchemaBackupRow {
  path: string;
  name: string;
  size_bytes: number;
  created_at: string;
}

export interface SchemaMigrationsResponse {
  migrations: SchemaMigrationRow[];
  backups: SchemaBackupRow[];
}

export interface CreateTableColumn {
  name: string;
  type: string;
  nullable?: boolean;
  default?: any;
  primary_key?: boolean;
}

export interface ColumnChangePayload {
  new_name?: string;
  new_type?: string;
  nullable?: boolean;
  default?: any;
}

interface ApiEnvelope<T> {
  success: boolean;
  message?: string;
  error?: string;
  data?: T;
  requires_reload?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AdminService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_URL}/admin`;

  getSettings(): Observable<AdminSettingsResponse> {
    return this.http.get<ApiEnvelope<AdminSettingsResponse>>(`${this.baseUrl}/settings`).pipe(
      map(r => {
        if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to load settings');
        return r.data;
      }),
      catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to load settings'))))
    );
  }

  updateSection(section: string, value: any): Observable<{ section: string; value: any }> {
    return this.http
      .put<ApiEnvelope<{ section: string; value: any }>>(`${this.baseUrl}/settings/${encodeURIComponent(section)}`, { value })
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Save failed');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Save failed'))))
      );
  }

  getImportSchema(): Observable<ImportSchemaResponse> {
    return this.http.get<ApiEnvelope<ImportSchemaResponse>>(`${this.baseUrl}/import-schema`).pipe(
      map(r => {
        if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to load schema');
        return r.data;
      }),
      catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to load schema'))))
    );
  }

  getLlmConfig(): Observable<LlmConfigResponse> {
    return this.http.get<ApiEnvelope<LlmConfigResponse>>(`${this.baseUrl}/llm`).pipe(
      map(r => {
        if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to load LLM config');
        return r.data;
      }),
      catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to load LLM config'))))
    );
  }

  updateLlmConfig(payload: LlmConfigUpdatePayload): Observable<LlmConfigResponse> {
    return this.http.put<ApiEnvelope<{ default: string; providers: Record<string, LlmProviderConfig> }>>(`${this.baseUrl}/llm`, payload).pipe(
      map(r => {
        if (!r.success || !r.data) throw new Error(r.message || r.error || 'Save failed');
        return { ...r.data, registered: [], api_keys: {}, schema: {} } as unknown as LlmConfigResponse;
      }),
      catchError(err => throwError(() => new Error(this.extractError(err, 'Save failed'))))
    );
  }

  testLlmProvider(name: string): Observable<LlmTestResponse> {
    return this.http
      .post<LlmTestResponse>(`${this.baseUrl}/llm/test/${encodeURIComponent(name)}`, {})
      .pipe(
        catchError(err => throwError(() => new Error(this.extractError(err, 'Connectivity test failed'))))
      );
  }

  // -----------------------------------------------------------------
  // Schema management — runtime DDL on the local SQLite database
  // -----------------------------------------------------------------
  listSchemaTables(): Observable<SchemaTableSummary[]> {
    return this.http
      .get<ApiEnvelope<{ tables: SchemaTableSummary[] }>>(`${this.baseUrl}/schema/tables`)
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to list tables');
          return r.data.tables;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to list tables'))))
      );
  }

  getSchemaTable(name: string): Observable<SchemaTable> {
    return this.http
      .get<ApiEnvelope<SchemaTable>>(`${this.baseUrl}/schema/tables/${encodeURIComponent(name)}`)
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to fetch table');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to fetch table'))))
      );
  }

  createSchemaTable(name: string, columns: CreateTableColumn[]): Observable<SchemaTable> {
    return this.http
      .post<ApiEnvelope<SchemaTable>>(`${this.baseUrl}/schema/tables`, { name, columns })
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to create table');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to create table'))))
      );
  }

  dropSchemaTable(name: string): Observable<{ dropped: boolean; table: string }> {
    return this.http
      .delete<ApiEnvelope<{ dropped: boolean; table: string }>>(`${this.baseUrl}/schema/tables/${encodeURIComponent(name)}`)
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to drop table');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to drop table'))))
      );
  }

  addSchemaColumn(table: string, column: CreateTableColumn): Observable<SchemaTable> {
    return this.http
      .post<ApiEnvelope<SchemaTable>>(`${this.baseUrl}/schema/tables/${encodeURIComponent(table)}/columns`, column)
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to add column');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to add column'))))
      );
  }

  updateSchemaColumn(table: string, column: string, payload: ColumnChangePayload): Observable<SchemaTable> {
    return this.http
      .put<ApiEnvelope<SchemaTable>>(`${this.baseUrl}/schema/tables/${encodeURIComponent(table)}/columns/${encodeURIComponent(column)}`, payload)
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to update column');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to update column'))))
      );
  }

  dropSchemaColumn(table: string, column: string): Observable<SchemaTable> {
    return this.http
      .delete<ApiEnvelope<SchemaTable>>(`${this.baseUrl}/schema/tables/${encodeURIComponent(table)}/columns/${encodeURIComponent(column)}`)
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to drop column');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to drop column'))))
      );
  }

  listSchemaMigrations(): Observable<SchemaMigrationsResponse> {
    return this.http
      .get<ApiEnvelope<SchemaMigrationsResponse>>(`${this.baseUrl}/schema/migrations`)
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Failed to load migrations');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Failed to load migrations'))))
      );
  }

  createSchemaBackup(): Observable<{ path: string; size_bytes: number }> {
    return this.http
      .post<ApiEnvelope<{ path: string; size_bytes: number }>>(`${this.baseUrl}/schema/backup`, {})
      .pipe(
        map(r => {
          if (!r.success || !r.data) throw new Error(r.message || r.error || 'Backup failed');
          return r.data;
        }),
        catchError(err => throwError(() => new Error(this.extractError(err, 'Backup failed'))))
      );
  }

  private extractError(err: any, fallback: string): string {
    return err?.error?.message || err?.error?.error || err?.message || fallback;
  }
}
