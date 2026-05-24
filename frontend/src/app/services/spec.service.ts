import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_URL } from '../app-settings';

export interface Spec {
  id?: number;
  spec_id: string;
  title: string;
  description?: string;
  category?: string;
  version?: string;
  status?: string;
  file_url?: string;
}

export interface ApiResponse<T> { success: boolean; message?: string; data?: T; count?: number; error?: string }

@Injectable({ providedIn: 'root' })
export class SpecService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_URL}/specs`;

  getSpecs(): Observable<Spec[]> {
    return new Observable<Spec[]>((observer) => {
      this.http.get<ApiResponse<Spec[]>>(`${this.baseUrl}/`).subscribe({
        next: (res) => observer.next(res.data || []),
        error: (err) => { console.error(err); observer.next([]); }
      });
    });
  }

  createSpec(payload: Spec): Observable<Spec> {
    return new Observable<Spec>((observer) => {
      this.http.post<ApiResponse<Spec>>(`${this.baseUrl}/`, payload).subscribe({
        next: (res) => observer.next((res.data as Spec) || payload),
        error: (err) => observer.error(err)
      });
    });
  }

  importSpecs(file: File): Observable<{ file_url: string }> {
    const form = new FormData();
    form.append('file', file);
    return new Observable((observer) => {
      this.http.post<ApiResponse<{ file_url: string }>>(`${this.baseUrl}/import`, form).subscribe({
        next: (res) => observer.next(res.data as any),
        error: (err) => observer.error(err)
      });
    });
  }
}








