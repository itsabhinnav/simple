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
  requirement_type?: string;
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

  createRequirement(data: RequirementCreateRequest): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/requirements`, data)
      .pipe(
        map((response: any) => {
          console.log('Create requirement response:', response);
          if (response.success && response.data) {
            return response.data;
          } else {
            throw new Error(response.message || response.error || 'Failed to create requirement');
          }
        }),
        catchError((error) => {
          console.error('Error creating requirement:', error);
          const errorMessage = error?.error?.message || error?.error?.error || error?.message || 'Failed to create requirement';
          throw new Error(errorMessage);
        })
      );
  }

  updateRequirement(id: number, data: RequirementUpdateRequest): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}/requirements/${id}`, data)
      .pipe(
        map((response: any) => {
          console.log('Update requirement response:', response);
          if (response.success && response.data) {
            return response.data;
          } else {
            throw new Error(response.message || response.error || 'Failed to update requirement');
          }
        }),
        catchError((error) => {
          console.error('Error updating requirement:', error);
          const errorMessage = error?.error?.message || error?.error?.error || error?.message || 'Failed to update requirement';
          throw new Error(errorMessage);
        })
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

