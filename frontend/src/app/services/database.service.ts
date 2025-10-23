import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

export interface Database {
  name: string;
  environment: string;
  size: number;
  checksum: string;
  created_date: string;
  modified_date: string;
}

export interface DatabaseInfo {
  database: Database;
  environment: string;
}

export interface QueryResult {
  success: boolean;
  data: {
    columns: string[];
    data: any[];
    row_count: number;
  };
}

export interface SyncResult {
  message: string;
  database: string;
  environment: string;
  synced: boolean;
}

export interface HealthStatus {
  status: string;
  artifactory: string;
  mock_mode: boolean;
  timestamp: string;
}

@Injectable({
  providedIn: 'root'
})
export class DatabaseService {
  private http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:5000/api';
  
  private databasesSubject = new BehaviorSubject<Database[]>([]);
  public databases$ = this.databasesSubject.asObservable();

  constructor() {
    this.loadDatabases();
  }

  /**
   * Get application health status
   */
  getHealthStatus(): Observable<HealthStatus> {
    return this.http.get<HealthStatus>(`${this.baseUrl}/health`).pipe(
      catchError(() => of({
        status: 'unhealthy',
        artifactory: 'disconnected',
        mock_mode: true,
        timestamp: new Date().toISOString()
      }))
    );
  }

  /**
   * Load all databases from the API
   */
  loadDatabases(environment: string = 'default'): void {
    const params = new HttpParams().set('environment', environment);
    
    this.http.get<{data: string[], success: boolean}>(`${this.baseUrl}/databases`, { params })
      .pipe(
        map(response => response.data.map(name => ({ name, environment, size: 0, checksum: '', created_date: '', modified_date: '' }))),
        catchError(() => of([]))
      )
      .subscribe(databases => {
        this.databasesSubject.next(databases);
      });
  }

  /**
   * Get databases as Observable
   */
  getDatabases(environment: string = 'default'): Observable<Database[]> {
    const params = new HttpParams().set('environment', environment);
    
    return this.http.get<{data: string[], success: boolean}>(`${this.baseUrl}/databases`, { params })
      .pipe(
        map(response => response.data.map(name => ({ name, environment, size: 0, checksum: '', created_date: '', modified_date: '' }))),
        catchError(() => of([]))
      );
  }

  /**
   * Get specific database information
   */
  getDatabaseInfo(dbName: string, environment: string = 'default'): Observable<DatabaseInfo> {
    const params = new HttpParams().set('environment', environment);
    
    return this.http.get<DatabaseInfo>(`${this.baseUrl}/databases/${dbName}`, { params });
  }

  /**
   * Sync database with Artifactory
   */
  syncDatabase(dbName: string, environment: string = 'default'): Observable<SyncResult> {
    const params = new HttpParams().set('environment', environment);
    
    return this.http.post<SyncResult>(`${this.baseUrl}/databases/${dbName}/sync`, {}, { params });
  }

  /**
   * Execute SQL query on database
   */
  executeQuery(dbName: string, query: string, environment: string = 'default'): Observable<QueryResult> {
    const params = new HttpParams().set('environment', environment);
    
    return this.http.post<QueryResult>(`${this.baseUrl}/databases/${dbName}/query`, {
      query: query,
      fetch_all: true
    }, { params });
  }

  /**
   * Format file size for display
   */
  formatFileSize(bytes: number | undefined | null): string {
    if (!bytes || bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * Format date for display
   */
  formatDate(dateString: string | undefined | null): string {
    if (!dateString) return 'Unknown';
    
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  }

  /**
   * Get current databases from subject
   */
  getCurrentDatabases(): Database[] {
    return this.databasesSubject.value;
  }
}
