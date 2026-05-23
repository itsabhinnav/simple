import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map, catchError } from 'rxjs';
import { of } from 'rxjs';

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
  private readonly baseUrl = 'http://localhost:5000/api';

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
   * Extract maximum ID number from requirements (REQ_XXXX format)
   */
  private getMaxIdFromRequirements(requirements: any[]): number {
    let maxId = 0;
    for (const req of requirements) {
      const reqId = req.requirement_id || '';
      const match = reqId.match(/REQ[_-]?(\d+)/i);
      if (match) {
        const num = parseInt(match[1], 10);
        if (!isNaN(num) && num > maxId) {
          maxId = num;
        }
      }
    }
    return maxId;
  }

  /**
   * Extract maximum ID number from test cases (TC_XXXX format)
   */
  private getMaxIdFromTestCases(testCases: any[]): number {
    let maxId = 0;
    for (const tc of testCases) {
      const tcId = tc.test_case_id || '';
      // Match TC_XXXX, TC-XXXX, or TCXXXX format
      const match = tcId.match(/TC[_-]?(\d+)/i);
      if (match) {
        const num = parseInt(match[1], 10);
        if (!isNaN(num) && num > maxId) {
          maxId = num;
        }
      }
    }
    return maxId;
  }

  /**
   * Extract maximum ID number from design tickets (DT_XXXX format)
   */
  private getMaxIdFromDesignTickets(designs: any[]): number {
    let maxId = 0;
    for (const design of designs) {
      const designId = design.design_ticket_id || '';
      // Match DT_XXXX, DT-XXXX, or DTXXXX format
      const match = designId.match(/DT[_-]?(\d+)/i);
      if (match) {
        const num = parseInt(match[1], 10);
        if (!isNaN(num) && num > maxId) {
          maxId = num;
        }
      }
    }
    return maxId;
  }
}

