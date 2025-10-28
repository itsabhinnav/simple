import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

export interface DesignTicket {
  id?: number;
  design_ticket_id: string;
  title: string;
  description?: string;
  design_type?: string;
  diagram_type?: string;
  image_url?: string;
  priority: string;
  status: string;
  linked_requirement_id?: string;
  assignee?: string;
  tags?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface DesignTicketCreateRequest {
  design_ticket_id: string;
  title: string;
  description?: string;
  design_type?: string;
  diagram_type?: string;
  image_url?: string;
  priority: string;
  status: string;
  linked_requirement_id?: string;
  assignee?: string;
  tags?: string;
}

export interface DesignTicketUpdateRequest {
  title?: string;
  description?: string;
  design_type?: string;
  diagram_type?: string;
  image_url?: string;
  priority?: string;
  status?: string;
  linked_requirement_id?: string;
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
export class DesignTicketService {
  private http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:5000/api';

  getDesignTickets(): Observable<DesignTicket[]> {
    return this.http.get<ApiResponse<DesignTicket[]>>(`${this.baseUrl}/design-tickets`)
      .pipe(
        map(response => response.data || []),
        catchError((error) => {
          console.error('Error loading design tickets:', error);
          return of([]);
        })
      );
  }

  getDesignTicketById(id: number): Observable<DesignTicket | null> {
    return this.http.get<ApiResponse<DesignTicket>>(`${this.baseUrl}/design-tickets/${id}`)
      .pipe(
        map(response => response.data || null),
        catchError(() => of(null))
      );
  }

  createDesignTicket(data: DesignTicketCreateRequest): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/design-tickets`, data)
      .pipe(
        map((response: any) => {
          if (response.success && response.data) {
            return response.data;
          } else {
            throw new Error(response.message || response.error || 'Failed to create design ticket');
          }
        }),
        catchError((error) => {
          console.error('Error creating design ticket:', error);
          const errorMessage = error?.error?.message || error?.error?.error || error?.message || 'Failed to create design ticket';
          throw new Error(errorMessage);
        })
      );
  }

  updateDesignTicket(id: number, data: DesignTicketUpdateRequest): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}/design-tickets/${id}`, data)
      .pipe(
        map((response: any) => {
          if (response.success && response.data) {
            return response.data;
          } else {
            throw new Error(response.message || response.error || 'Failed to update design ticket');
          }
        }),
        catchError((error) => {
          console.error('Error updating design ticket:', error);
          const errorMessage = error?.error?.message || error?.error?.error || error?.message || 'Failed to update design ticket';
          throw new Error(errorMessage);
        })
      );
  }

  deleteDesignTicket(id: number): Observable<boolean> {
    return this.http.delete<ApiResponse<any>>(`${this.baseUrl}/design-tickets/${id}`)
      .pipe(
        map(response => response.success || false),
        catchError(() => of(false))
      );
  }
}

