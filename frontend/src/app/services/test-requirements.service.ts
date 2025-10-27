import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class TestRequirementsService {
  private http = inject(HttpClient);
  
  testConnection(): Observable<any> {
    console.log('Testing requirements API...');
    return this.http.get('http://localhost:5000/api/requirements').pipe(
      tap({
        next: (data) => console.log('Requirements API Response:', data),
        error: (err) => console.error('Requirements API Error:', err)
      })
    );
  }
}

