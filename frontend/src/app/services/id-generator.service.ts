import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map, catchError } from 'rxjs';
import { of } from 'rxjs';
import { API_URL } from '../app-settings';

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
export class IdGeneratorService {
  private http = inject(HttpClient);
  private readonly baseUrl = API_URL;

  /**
   * Generate next Requirement ID in format REQ_XXXX
   */
  generateNextRequirementId(): Observable<string> {
    return this.http.get<ApiResponse<any[]>>(`${this.baseUrl}/requirements`)
      .pipe(
        map(response => {
          const requirements = response.data || [];
          const maxId = this.getMaxIdFromRequirements(requirements);
          const nextNumber = maxId + 1;
          return `REQ_${nextNumber.toString().padStart(4, '0')}`;
        }),
        catchError(() => {
          // On error, start from REQ_0001
          return of('REQ_0001');
        })
      );
  }

  /**
   * Generate next Test Case ID in format TC_XXXX
   */
  generateNextTestCaseId(): Observable<string> {
    return this.http.get<ApiResponse<any[]>>(`${this.baseUrl}/test-cases/`)
      .pipe(
        map(response => {
          const testCases = response.data || [];
          const maxId = this.getMaxIdFromTestCases(testCases);
          const nextNumber = maxId + 1;
          return `TC_${nextNumber.toString().padStart(4, '0')}`;
        }),
        catchError(() => {
          // On error, start from TC_0001
          return of('TC_0001');
        })
      );
  }

  /**
   * Generate next Design Ticket ID in format DT_XXXX
   */
  generateNextDesignTicketId(): Observable<string> {
    return this.http.get<ApiResponse<any[]>>(`${this.baseUrl}/design-tickets`)
      .pipe(
        map(response => {
          const designs = response.data || [];
          const maxId = this.getMaxIdFromDesignTickets(designs);
          const nextNumber = maxId + 1;
          return `DT_${nextNumber.toString().padStart(4, '0')}`;
        }),
        catchError(() => {
          // On error, start from DT_0001
          return of('DT_0001');
        })
      );
  }

  /**
   * Pull the trailing numeric suffix off of an ID string.
   *
   * Handles both flat (`REQ_0001`) and feature-segmented
   * (`TC_AAOS_BT_001`) conventions — anything that ends with
   * `[_-]?<digits>` counts. The old per-prefix regex (e.g. `TC[_-]?(\d+)`)
   * silently returned 0 for IDs like `TC_AAOS_BT_001`, which made the next
   * generated ID collide-by-prefix and (worse) reset the counter to 0001,
   * then the backend rejected it for failing the format check.
   */
  private trailingNumber(id: string): number | null {
    if (!id) return null;
    const match = id.match(/(\d+)\s*$/);
    if (!match) return null;
    const num = parseInt(match[1], 10);
    return isNaN(num) ? null : num;
  }

  private getMaxIdFromRequirements(requirements: any[]): number {
    let maxId = 0;
    for (const req of requirements) {
      const num = this.trailingNumber(req?.requirement_id || '');
      if (num !== null && num > maxId) maxId = num;
    }
    return maxId;
  }

  private getMaxIdFromTestCases(testCases: any[]): number {
    let maxId = 0;
    for (const tc of testCases) {
      const num = this.trailingNumber(tc?.test_case_id || '');
      if (num !== null && num > maxId) maxId = num;
    }
    return maxId;
  }

  private getMaxIdFromDesignTickets(designs: any[]): number {
    let maxId = 0;
    for (const design of designs) {
      const num = this.trailingNumber(design?.design_ticket_id || '');
      if (num !== null && num > maxId) maxId = num;
    }
    return maxId;
  }
}

