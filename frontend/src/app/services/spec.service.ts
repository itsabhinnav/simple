import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_URL } from '../app-settings';

export interface Spec {
  id?: number;
  spec_id: string;
  title: string;
  project?: string;
  tags?: string;
  category?: string;
  version?: string;
  status?: string;
  file_url?: string;
  file_name?: string;
  source_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SpecProjectSummary {
  project: string;
  spec_count: number;
  spec_families: number;
  last_updated?: string;
}

export interface SpecCreatePayload {
  spec_id: string;
  title: string;
  project?: string;
  tags?: string;
  category?: string;
  version?: string;
  status?: string;
  source_url?: string;
}

export interface ApiResponse<T> { success: boolean; message?: string; data?: T; count?: number; error?: string }

@Injectable({ providedIn: 'root' })
export class SpecService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_URL}/specs`;

  getSpecs(search?: string, project?: string): Observable<Spec[]> {
    const params: Record<string, string> = {};
    if (search?.trim()) params['search'] = search.trim();
    if (project?.trim()) params['project'] = project.trim();
    return new Observable<Spec[]>((observer) => {
      this.http.get<ApiResponse<Spec[]>>(`${this.baseUrl}/`, { params }).subscribe({
        next: (res) => observer.next(res.data || []),
        error: (err) => { console.error(err); observer.next([]); }
      });
    });
  }

  getProjects(): Observable<SpecProjectSummary[]> {
    return new Observable<SpecProjectSummary[]>((observer) => {
      this.http.get<ApiResponse<SpecProjectSummary[]>>(`${this.baseUrl}/projects`).subscribe({
        next: (res) => observer.next(res.data || []),
        error: (err) => { console.error(err); observer.next([]); }
      });
    });
  }

  getSpecVersions(specId: string, project?: string): Observable<Spec[]> {
    const params: Record<string, string> = { spec_id: specId };
    if (project?.trim()) params['project'] = project.trim();
    return new Observable<Spec[]>((observer) => {
      this.http.get<ApiResponse<Spec[]>>(`${this.baseUrl}/versions`, { params }).subscribe({
        next: (res) => observer.next(res.data || []),
        error: (err) => { console.error(err); observer.next([]); }
      });
    });
  }

  createSpec(payload: SpecCreatePayload, file?: File): Observable<Spec> {
    return new Observable<Spec>((observer) => {
      if (file) {
        const form = new FormData();
        form.append('data', JSON.stringify(payload));
        form.append('file', file);
        this.http.post<ApiResponse<Spec>>(`${this.baseUrl}/`, form).subscribe({
          next: (res) => {
            if (!res.success || !res.data?.id) {
              observer.error(new Error(res.error || res.message || 'Failed to add spec'));
              return;
            }
            observer.next(res.data as Spec);
          },
          error: (err) => {
            const msg = err?.error?.message || err?.message || 'Failed to add spec';
            observer.error(new Error(msg));
          }
        });
      } else {
        this.http.post<ApiResponse<Spec>>(`${this.baseUrl}/`, payload).subscribe({
          next: (res) => {
            if (!res.success || !res.data?.id) {
              observer.error(new Error(res.error || res.message || 'Failed to add spec'));
              return;
            }
            observer.next(res.data as Spec);
          },
          error: (err) => {
            const msg = err?.error?.message || err?.message || 'Failed to add spec';
            observer.error(new Error(msg));
          }
        });
      }
    });
  }

  downloadSpecFile(specId: number, fileName?: string): void {
    this.http.get(`${this.baseUrl}/${specId}/file`, { responseType: 'blob' }).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = fileName || 'spec-document';
        anchor.click();
        window.URL.revokeObjectURL(url);
      },
      error: (err) => console.error('Download failed', err)
    });
  }

  importSpecs(file: File): Observable<{ file_url: string }> {
    const form = new FormData();
    form.append('file', file);
    return new Observable((observer) => {
      this.http.post<ApiResponse<{ file_url: string }>>(`${this.baseUrl}/import/legacy`, form).subscribe({
        next: (res) => observer.next(res.data as { file_url: string }),
        error: (err) => observer.error(err)
      });
    });
  }

  specVersionLabel(spec: Spec): string {
    const version = spec.version ? `v${spec.version}` : 'v?';
    const project = spec.project ? ` · ${spec.project}` : '';
    return `${spec.spec_id} ${version} — ${spec.title}${project}`;
  }
}
