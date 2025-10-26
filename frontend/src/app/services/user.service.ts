import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

export interface User {
  id?: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role?: string;
  created_at?: string;
  updated_at?: string;
  email_masked?: string;
  full_name?: string;
  is_active?: boolean;
}

export interface UserCreateRequest {
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role?: string;
}

export interface UserUpdateRequest {
  username?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  role?: string;
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
export class UserService {
  private http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:5000/api';
  
  private usersSubject = new BehaviorSubject<User[]>([]);
  public users$ = this.usersSubject.asObservable();

  constructor() {
    this.loadUsers();
  }

  /**
   * Load all users from the API
   */
  loadUsers(): void {
    this.http.get<ApiResponse<User[]>>(`${this.baseUrl}/users`)
      .pipe(
        map(response => response.data || []),
        catchError(() => of([]))
      )
      .subscribe(users => {
        this.usersSubject.next(users);
      });
  }

  /**
   * Get all users as Observable
   */
  getUsers(): Observable<User[]> {
    return this.http.get<ApiResponse<User[]>>(`${this.baseUrl}/users`)
      .pipe(
        map(response => response.data || []),
        catchError(() => of([]))
      );
  }

  /**
   * Get user by ID
   */
  getUserById(id: number): Observable<User | null> {
    return this.http.get<ApiResponse<User>>(`${this.baseUrl}/users/${id}`)
      .pipe(
        map(response => response.data || null),
        catchError(() => of(null))
      );
  }

  /**
   * Create a new user
   */
  createUser(userData: UserCreateRequest): Observable<User | null> {
    return this.http.post<ApiResponse<User>>(`${this.baseUrl}/users`, userData)
      .pipe(
        map(response => {
          if (response.success && response.data) {
            // Update local cache
            const currentUsers = this.usersSubject.value;
            this.usersSubject.next([response.data, ...currentUsers]);
            return response.data;
          }
          return null;
        }),
        catchError(error => {
          console.error('Error creating user:', error);
          return of(null);
        })
      );
  }

  /**
   * Update an existing user
   */
  updateUser(id: number, userData: UserUpdateRequest): Observable<User | null> {
    return this.http.put<ApiResponse<User>>(`${this.baseUrl}/users/${id}`, userData)
      .pipe(
        map(response => {
          if (response.success && response.data) {
            // Update local cache
            const currentUsers = this.usersSubject.value;
            const updatedUsers = currentUsers.map(user => 
              user.id === id ? response.data! : user
            );
            this.usersSubject.next(updatedUsers);
            return response.data;
          }
          return null;
        }),
        catchError(error => {
          console.error('Error updating user:', error);
          return of(null);
        })
      );
  }

  /**
   * Delete a user
   */
  deleteUser(id: number): Observable<boolean> {
    return this.http.delete<ApiResponse<any>>(`${this.baseUrl}/users/${id}`)
      .pipe(
        map(response => {
          if (response.success) {
            // Update local cache
            const currentUsers = this.usersSubject.value;
            const filteredUsers = currentUsers.filter(user => user.id !== id);
            this.usersSubject.next(filteredUsers);
            return true;
          }
          return false;
        }),
        catchError(() => of(false))
      );
  }

  /**
   * Get current users from subject
   */
  getCurrentUsers(): User[] {
    return this.usersSubject.value;
  }

  /**
   * Validate email format
   */
  isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Validate username format
   */
  isValidUsername(username: string): boolean {
    return username.length >= 1 && username.length <= 50 && /^[a-zA-Z0-9_]+$/.test(username);
  }

  /**
   * Check if username is available
   */
  isUsernameAvailable(username: string, currentUserId?: number): boolean {
    const currentUsers = this.usersSubject.value;
    return !currentUsers.some(user => 
      user.username.toLowerCase() === username.toLowerCase() && 
      user.id !== currentUserId
    );
  }
}
