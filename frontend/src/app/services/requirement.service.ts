import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

export interface Requirement {
  id?: number;
  requirement_id: string;
  title: string;
  description?: string;
  given?: string;
  when_action?: string;
  then_result?: string;
  priority: string;
  status: string;
  assignee?: string;
  tags?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface RequirementCreateRequest {
  requirement_id: string;
  title: string;
  description?: string;
  given?: string;
  when?: string;
  then?: string;
  priority: string;
  status: string;
  assignee?: string;
  tags?: string;
}

export interface RequirementUpdateRequest {
  title?: string;
  description?: string;
  given?: string;
  when?: string;
  then?: string;
  priority?: string;
  status?: string;
  assignee?: string;
  tags?: string;
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
export class RequirementService {
  private http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:5000/api';

  getRequirements(): Observable<Requirement[]> {
    return this.http.get<ApiResponse<Requirement[]>>(`${this.baseUrl}/requirements`)
      .pipe(
        map(response => {
          console.log('Requirements API response:', response);
          return response.data || [];
        }),
        catchError((error) => {
          console.error('Error loading requirements:', error);
          return of([]);
        })
      );
  }

  getRequirementById(id: number): Observable<Requirement | null> {
    return this.http.get<ApiResponse<Requirement>>(`${this.baseUrl}/requirements/${id}`)
      .pipe(
        map(response => response.data || null),
        catchError(() => of(null))
      );
  }

  createRequirement(data: RequirementCreateRequest): Observable<Requirement | null> {
    return this.http.post<ApiResponse<Requirement>>(`${this.baseUrl}/requirements`, data)
      .pipe(
        map(response => response.data || null),
        catchError(() => of(null))
      );
  }

  updateRequirement(id: number, data: RequirementUpdateRequest): Observable<Requirement | null> {
    return this.http.put<ApiResponse<Requirement>>(`${this.baseUrl}/requirements/${id}`, data)
      .pipe(
        map(response => response.data || null),
        catchError(() => of(null))
      );
  }

  deleteRequirement(id: number): Observable<boolean> {
    return this.http.delete<ApiResponse<any>>(`${this.baseUrl}/requirements/${id}`)
      .pipe(
        map(response => response.success || false),
        catchError(() => of(false))
      );
  }
}

