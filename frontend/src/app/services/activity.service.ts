import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { API_URL } from '../app-settings';

/**
 * Git-style change-log record. The backend writes one of these every
 * time an entity is created / updated / deleted / restored.
 */
export interface ActivityCommit {
  id: number;
  commit_hash: string;
  parent_hash?: string | null;
  entity_type: string;
  entity_id: string;
  entity_pk?: number | null;
  action: 'create' | 'update' | 'delete' | 'restore' | string;
  field_changes: Record<string, { old: any; new: any }>;
  snapshot_before?: any;
  snapshot_after?: any;
  summary: string;
  author_username: string;
  author_id?: number | null;
  created_at: string;
}

interface ActivityListResponse {
  success: boolean;
  data: ActivityCommit[];
  count: number;
}

interface ActivityCommitResponse {
  success: boolean;
  data: ActivityCommit;
  message?: string;
  error?: string;
}

@Injectable({ providedIn: 'root' })
export class ActivityService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_URL}/activity`;

  /** Per-entity history, newest first. */
  getForEntity(
    entityType: string,
    entityId: string | number,
    opts: { limit?: number; offset?: number } = {}
  ): Observable<ActivityCommit[]> {
    const params: string[] = [];
    if (opts.limit != null) params.push(`limit=${opts.limit}`);
    if (opts.offset != null) params.push(`offset=${opts.offset}`);
    const qs = params.length ? `?${params.join('&')}` : '';
    return this.http
      .get<ActivityListResponse>(
        `${this.baseUrl}/${encodeURIComponent(entityType)}/${encodeURIComponent(String(entityId))}${qs}`
      )
      .pipe(
        map(r => r.data || []),
        catchError(() => of([]))
      );
  }

  /** Global activity feed. */
  getRecent(opts: { entityType?: string; limit?: number; offset?: number } = {}): Observable<ActivityCommit[]> {
    const params: string[] = [];
    if (opts.entityType) params.push(`entity_type=${encodeURIComponent(opts.entityType)}`);
    if (opts.limit != null) params.push(`limit=${opts.limit}`);
    if (opts.offset != null) params.push(`offset=${opts.offset}`);
    const qs = params.length ? `?${params.join('&')}` : '';
    return this.http.get<ActivityListResponse>(`${this.baseUrl}${qs}`).pipe(
      map(r => r.data || []),
      catchError(() => of([]))
    );
  }

  /** Single-commit details (used by the diff modal). */
  getCommit(commitHash: string): Observable<ActivityCommit | null> {
    return this.http.get<ActivityCommitResponse>(`${this.baseUrl}/commit/${commitHash}`).pipe(
      map(r => r.data || null),
      catchError(() => of(null))
    );
  }

  /** Roll the entity back to a previous commit; returns the restored entity. */
  revertToCommit(commitHash: string): Observable<any> {
    return this.http.post<ActivityCommitResponse>(`${this.baseUrl}/commit/${commitHash}/revert`, {}).pipe(
      map(r => {
        if (!r.success) {
          throw new Error(r.error || r.message || 'Revert failed');
        }
        return r.data;
      })
    );
  }
}
