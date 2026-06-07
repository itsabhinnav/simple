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

interface ApiEnvelope<T> {
  success: boolean;
  message?: string;
  error?: string;
  data?: T;
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

  private extractError(err: any, fallback: string): string {
    return err?.error?.message || err?.error?.error || err?.message || fallback;
  }
}
