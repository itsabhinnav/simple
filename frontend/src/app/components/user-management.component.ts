import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { BulkImportResult, UserService, User, UserCreateRequest, UserUpdateRequest } from '../services/user.service';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-user-management',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="user-management-container">
      <!-- Header -->
      <header class="management-header">
        <div class="header-left">
          <nav class="breadcrumb">
            <a routerLink="/" class="breadcrumb-link">
              <i class="icon-database"></i>
              Dashboard
            </a>
            <span class="breadcrumb-separator">›</span>
            <span class="breadcrumb-current">User Management</span>
          </nav>
          <h1 class="page-title">
            <i class="icon-users"></i>
            User Management
          </h1>
        </div>
        <button 
          class="add-btn" 
          (click)="openCreateModal()"
          [disabled]="isLoading()">
          <i class="icon-plus"></i>
          Add New User
        </button>
      </header>

      <!-- Loading State (skeleton) -->
      <div *ngIf="isLoading()" class="skeleton-page" aria-busy="true" aria-label="Loading users">
        <div class="skeleton-card">
          <span class="skeleton-text is-title"></span>
          <span class="skeleton-text is-md"></span>
        </div>
        <div class="skeleton-card" style="padding:0;">
          <div class="skeleton-row" *ngFor="let _ of [1,2,3,4,5,6,7,8]">
            <span class="skeleton-circle"></span>
            <span class="skeleton-text is-md" style="flex:1;"></span>
            <span class="skeleton-text is-pill"></span>
            <span class="skeleton-text is-sm" style="width:90px;"></span>
          </div>
        </div>
      </div>

      <!-- Error State -->
      <div *ngIf="error()" class="error-container">
        <i class="icon-error"></i>
        <p>{{ error() }}</p>
        <button (click)="loadUsers()" class="retry-btn">Retry</button>
      </div>

      <!-- Bulk Import -->
      <section *ngIf="!isLoading()" class="import-panel">
        <div class="import-header">
          <div>
            <h2>Bulk Import</h2>
            <p>Specs, requirements, test cases, and design tickets</p>
          </div>
          <span class="import-count" *ngIf="selectedImportFiles().length">
            {{ selectedImportFiles().length }} file{{ selectedImportFiles().length === 1 ? '' : 's' }}
          </span>
        </div>

        <div class="import-controls">
          <label class="import-field">
            <span>Data type</span>
            <select class="form-select" [(ngModel)]="bulkImportTarget">
              <option value="auto">Auto by sheet name</option>
              <option value="specifications">Specifications</option>
              <option value="requirements">Requirements</option>
              <option value="test_cases">Test Cases</option>
              <option value="design_tickets">Design Tickets</option>
            </select>
          </label>

          <label class="file-picker">
            <input
              type="file"
              accept=".xlsx,.xlsm"
              multiple
              (change)="onBulkImportFilesSelected($event)">
            <i class="icon-upload"></i>
            Choose Excel files
          </label>

          <button
            type="button"
            class="btn-import"
            (click)="runBulkImport()"
            [disabled]="isImporting() || selectedImportFiles().length === 0">
            <span *ngIf="isImporting()" class="spinner-small"></span>
            Import
          </button>
        </div>

        <div class="selected-files" *ngIf="selectedImportFiles().length">
          <span *ngFor="let file of selectedImportFiles()">{{ file.name }}</span>
        </div>

        <div class="import-error" *ngIf="importError()">{{ importError() }}</div>

        <div class="import-result" *ngIf="importResult() as result">
          <div class="result-totals">
            <span><strong>{{ result.totals.created }}</strong> created</span>
            <span><strong>{{ result.totals.skipped }}</strong> skipped</span>
            <span><strong>{{ result.totals.failed }}</strong> failed</span>
          </div>

          <div class="result-files">
            <div class="result-file" *ngFor="let file of result.files">
              <strong>{{ file.file }}</strong>
              <span>{{ file.created }} created, {{ file.skipped }} skipped, {{ file.failed }} failed</span>
              <ul *ngIf="file.errors.length">
                <li *ngFor="let item of file.errors.slice(0, 5)">
                  {{ item.sheet ? item.sheet + ' - ' : '' }}{{ item.row ? 'Row ' + item.row + ': ' : '' }}{{ item.error }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- Users Table -->
      <div *ngIf="!isLoading() && !error()" class="table-container">
        <div class="table-header">
          <h3>Users ({{ users().length }})</h3>
          <div class="search-box">
            <input 
              type="text" 
              placeholder="Search users..." 
              [(ngModel)]="searchTerm"
              class="search-input">
          </div>
        </div>

        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Email</th>
                <th>Full Name</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let user of filteredUsers()">
                <td>{{ user.id }}</td>
                <td>{{ user.username }}</td>
                <td>{{ user.email_masked || user.email }}</td>
                <td>{{ user.full_name || 'N/A' }}</td>
                <td>
                  <span class="role-badge" [class]="'role-' + (user.role || 'user')">
                    {{ user.role || 'user' }}
                  </span>
                </td>
                <td>
                  <span class="status-badge" [class]="user.is_active ? 'active' : 'inactive'">
                    {{ user.is_active ? 'Active' : 'Inactive' }}
                  </span>
                </td>
                <td class="actions">
                  <button 
                    class="btn-edit" 
                    (click)="openEditModal(user)"
                    title="Edit User">
                    <i class="icon-edit"></i>
                  </button>
                  <button 
                    class="btn-delete" 
                    (click)="confirmDelete(user)"
                    title="Delete User"
                    [disabled]="user.role === 'admin'">
                    <i class="icon-delete"></i>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Empty State -->
        <div *ngIf="filteredUsers().length === 0" class="empty-state">
          <i class="icon-empty"></i>
          <h3>No Users Found</h3>
          <p *ngIf="searchTerm">No users match your search criteria.</p>
          <p *ngIf="!searchTerm">No users available. Create your first user!</p>
        </div>
      </div>

      <!-- Create/Edit Modal -->
      <div *ngIf="showModal()" class="modal-overlay" (click)="closeModal()">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <h2>{{ isEditMode() ? 'Edit User' : 'Create New User' }}</h2>
            <button class="close-btn" (click)="closeModal()">
              <i class="icon-close"></i>
            </button>
          </div>

          <form [formGroup]="userForm" (ngSubmit)="onSubmit()" class="modal-body">
            <div class="form-group">
              <label for="username">Username *</label>
              <input 
                type="text" 
                id="username"
                formControlName="username"
                class="form-input"
                [class.error]="userForm.get('username')?.invalid && userForm.get('username')?.touched">
              <div *ngIf="userForm.get('username')?.invalid && userForm.get('username')?.touched" class="error-message">
                <span *ngIf="userForm.get('username')?.errors?.['required']">Username is required</span>
                <span *ngIf="userForm.get('username')?.errors?.['minlength']">Username must be at least 1 character</span>
                <span *ngIf="userForm.get('username')?.errors?.['maxlength']">Username must be at most 50 characters</span>
                <span *ngIf="userForm.get('username')?.errors?.['pattern']">Username can only contain letters, numbers, and underscores</span>
                <span *ngIf="userForm.get('username')?.errors?.['usernameExists']">Username already exists</span>
              </div>
            </div>

            <div class="form-group">
              <label for="email">Email *</label>
              <input 
                type="email" 
                id="email"
                formControlName="email"
                class="form-input"
                [class.error]="userForm.get('email')?.invalid && userForm.get('email')?.touched">
              <div *ngIf="userForm.get('email')?.invalid && userForm.get('email')?.touched" class="error-message">
                <span *ngIf="userForm.get('email')?.errors?.['required']">Email is required</span>
                <span *ngIf="userForm.get('email')?.errors?.['email']">Please enter a valid email address</span>
                <span *ngIf="userForm.get('email')?.errors?.['emailExists']">Email already exists</span>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="firstName">First Name</label>
                <input 
                  type="text" 
                  id="firstName"
                  formControlName="first_name"
                  class="form-input">
              </div>
              <div class="form-group">
                <label for="lastName">Last Name</label>
                <input 
                  type="text" 
                  id="lastName"
                  formControlName="last_name"
                  class="form-input">
              </div>
            </div>

            <div class="form-group">
              <label for="role">Role</label>
              <select 
                id="role"
                formControlName="role"
                class="form-select">
                <option value="">Select Role</option>
                <option value="admin">Admin</option>
                <option value="user">User</option>
                <option value="tester">Tester</option>
                <option value="developer">Developer</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>

            <div class="form-actions">
              <button 
                type="button" 
                class="btn-cancel" 
                (click)="closeModal()">
                Cancel
              </button>
              <button 
                type="submit" 
                class="btn-submit"
                [disabled]="userForm.invalid || isSubmitting()">
                <span *ngIf="isSubmitting()" class="spinner-small"></span>
                {{ isEditMode() ? 'Update User' : 'Create User' }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Delete Confirmation Modal -->
      <div *ngIf="showDeleteModalSignal()" class="modal-overlay" (click)="cancelDelete()">
        <div class="modal-content delete-modal" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <h2>Confirm Delete</h2>
            <button class="close-btn" (click)="cancelDelete()">
              <i class="icon-close"></i>
            </button>
          </div>
          <div class="modal-body">
            <p>Are you sure you want to delete user <strong>{{ userToDelete()?.username }}</strong>?</p>
            <p class="warning-text">This action cannot be undone.</p>
            <div class="form-actions">
              <button 
                type="button" 
                class="btn-cancel" 
                (click)="cancelDelete()">
                Cancel
              </button>
              <button 
                type="button" 
                class="btn-delete-confirm"
                (click)="deleteUser()"
                [disabled]="isDeleting()">
                <span *ngIf="isDeleting()" class="spinner-small"></span>
                Delete User
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .user-management-container {
      max-width: 100%;
      margin: 0 auto;
      padding: var(--spacing-md);
    }

    .management-header {
      background-color: var(--color-gray-100);
      border-bottom: 1px solid var(--color-gray-300);
      padding: var(--spacing-lg);
      margin-bottom: var(--spacing-lg);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .header-left {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .breadcrumb {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
      font-size: 14px;
      margin-bottom: var(--spacing-sm);
    }

    .breadcrumb-link {
      color: var(--color-primary-lighter);
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 5px;
      transition: color 0.2s;
    }

    .breadcrumb-link:hover {
      color: var(--color-primary);
    }

    .breadcrumb-separator {
      color: var(--color-gray-400);
    }

    .breadcrumb-current {
      color: var(--color-primary);
      font-weight: 500;
    }

    .page-title {
      margin: 0;
      font-size: 1.8rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--color-primary);
    }

    .add-btn {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
      padding: var(--spacing-sm) var(--spacing-md);
      background: var(--color-primary);
      color: var(--color-gray-100);
      border: 1px solid var(--color-primary);
      border-radius: var(--border-radius-sm);
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
    }

    .add-btn:hover:not(:disabled) {
      background: var(--color-primary-light);
      border-color: var(--color-primary-light);
    }

    .add-btn:disabled {
      background: var(--color-gray-400);
      border-color: var(--color-gray-400);
      cursor: not-allowed;
    }

    .loading-container, .error-container {
      text-align: center;
      padding: 60px 20px;
    }

    .spinner {
      width: 40px;
      height: 40px;
      border: 4px solid var(--color-gray-300);
      border-top: 4px solid var(--color-accent);
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }

    .spinner-small {
      width: 16px;
      height: 16px;
      border: 2px solid transparent;
      border-top: 2px solid currentColor;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      display: inline-block;
      margin-right: 8px;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .table-container {
      background: var(--color-gray-100);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius);
      padding: var(--spacing-lg);
    }

    .import-panel {
      background: var(--color-gray-100);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius);
      padding: var(--spacing-lg);
      margin-bottom: var(--spacing-lg);
    }

    .import-header {
      display: flex;
      justify-content: space-between;
      gap: var(--spacing-md);
      align-items: flex-start;
      margin-bottom: var(--spacing-md);
    }

    .import-header h2 {
      margin: 0 0 4px;
      color: var(--color-primary);
      font-size: 1.15rem;
    }

    .import-header p {
      margin: 0;
      color: var(--color-primary-lighter);
      font-size: 13px;
    }

    .import-count {
      color: var(--color-primary);
      background: var(--color-gray-200);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius-sm);
      padding: 6px 10px;
      font-size: 12px;
      white-space: nowrap;
    }

    .import-controls {
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(220px, 1fr) auto;
      gap: var(--spacing-md);
      align-items: end;
    }

    .import-field span {
      display: block;
      color: #333;
      font-weight: 500;
      margin-bottom: 5px;
    }

    .file-picker {
      min-height: 42px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-sm);
      padding: 10px 14px;
      border: 1px dashed var(--color-gray-400);
      border-radius: var(--border-radius-sm);
      color: var(--color-primary);
      background: var(--color-gray-200);
      cursor: pointer;
      font-weight: 500;
    }

    .file-picker input {
      display: none;
    }

    .btn-import {
      min-height: 42px;
      padding: 10px 18px;
      background: var(--color-primary);
      color: var(--color-gray-100);
      border: 1px solid var(--color-primary);
      border-radius: var(--border-radius-sm);
      cursor: pointer;
      font-weight: 500;
    }

    .btn-import:disabled {
      background: var(--color-gray-400);
      border-color: var(--color-gray-400);
      cursor: not-allowed;
    }

    .selected-files {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: var(--spacing-md);
    }

    .selected-files span {
      background: var(--color-gray-200);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius-sm);
      padding: 5px 8px;
      font-size: 12px;
    }

    .import-error {
      color: #c62828;
      margin-top: var(--spacing-md);
      font-weight: 500;
    }

    .import-result {
      margin-top: var(--spacing-md);
      border-top: 1px solid var(--color-gray-300);
      padding-top: var(--spacing-md);
    }

    .result-totals {
      display: flex;
      gap: var(--spacing-md);
      flex-wrap: wrap;
      margin-bottom: var(--spacing-md);
    }

    .result-totals span {
      background: var(--color-gray-200);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius-sm);
      padding: 6px 10px;
    }

    .result-files {
      display: grid;
      gap: 10px;
    }

    .result-file {
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius-sm);
      padding: 10px;
      display: grid;
      gap: 4px;
    }

    .result-file ul {
      margin: 6px 0 0;
      padding-left: 18px;
      color: #c62828;
      font-size: 12px;
    }

    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .table-header h3 {
      margin: 0;
      color: #333;
    }

    .search-box {
      position: relative;
    }

    .search-input {
      padding: var(--spacing-sm) var(--spacing-md);
      border: 1px solid var(--color-gray-300);
      border-radius: var(--border-radius-sm);
      width: 250px;
      font-size: 14px;
      background-color: var(--color-gray-100);
    }

    .search-input:focus {
      outline: none;
      border-color: var(--color-accent);
      box-shadow: 0 0 0 2px var(--color-accent-light);
    }

    .table-wrapper {
      overflow-x: auto;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
    }

    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }

    .data-table th {
      background: #f5f5f5;
      color: #333;
      font-weight: 600;
      padding: 12px 16px;
      text-align: left;
      border-bottom: 2px solid #e0e0e0;
      white-space: nowrap;
    }

    .data-table td {
      padding: 12px 16px;
      border-bottom: 1px solid #e0e0e0;
      vertical-align: top;
    }

    .data-table tbody tr:hover {
      background: #f9f9f9;
    }

    .data-table tbody tr:last-child td {
      border-bottom: none;
    }

    .role-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      text-transform: capitalize;
    }

    .role-admin { background: #ffebee; color: #c62828; }
    .role-user { background: #e3f2fd; color: #1976d2; }
    .role-tester { background: #f3e5f5; color: #7b1fa2; }
    .role-developer { background: #e8f5e8; color: #2e7d32; }
    .role-inactive { background: #fafafa; color: #757575; }

    .status-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }

    .status-badge.active { background: #e8f5e8; color: #2e7d32; }
    .status-badge.inactive { background: #ffebee; color: #c62828; }

    .actions {
      display: flex;
      gap: 8px;
    }

    .btn-edit, .btn-delete {
      padding: 6px 8px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.2s;
    }

    .btn-edit {
      background: var(--color-accent-light);
      color: var(--color-accent-hover);
    }

    .btn-edit:hover {
      background: var(--color-accent-light);
      opacity: 0.8;
    }

    .btn-delete {
      background: transparent;
      color: var(--color-primary-lighter);
      border: 1px solid var(--color-gray-300);
    }

    .btn-delete:hover:not(:disabled) {
      background: var(--color-gray-200);
      border-color: var(--color-gray-400);
    }

    .btn-delete:disabled {
      background: transparent;
      color: var(--color-gray-400);
      border-color: var(--color-gray-300);
      cursor: not-allowed;
    }

    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: #666;
    }

    .retry-btn {
      background: #2196f3;
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
      margin-top: 15px;
    }

    .retry-btn:hover {
      background: #1976d2;
    }

    /* Modal Styles */
    .modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }

    .modal-content {
      background: white;
      border-radius: 12px;
      width: 90%;
      max-width: 500px;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    }

    .delete-modal {
      max-width: 400px;
    }

    .modal-header {
      padding: 20px;
      border-bottom: 1px solid #e0e0e0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .modal-header h2 {
      margin: 0;
      color: #333;
    }

    .close-btn {
      background: none;
      border: none;
      font-size: 20px;
      cursor: pointer;
      color: #666;
      padding: 0;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .close-btn:hover {
      color: #333;
    }

    .modal-body {
      padding: 20px;
    }

    .form-group {
      margin-bottom: 20px;
    }

    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 15px;
    }

    .form-group label {
      display: block;
      margin-bottom: 5px;
      font-weight: 500;
      color: #333;
    }

    .form-input, .form-select {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #ddd;
      border-radius: 6px;
      font-size: 14px;
      transition: border-color 0.2s;
    }

    .form-input:focus, .form-select:focus {
      outline: none;
      border-color: #2196f3;
      box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.2);
    }

    .form-input.error {
      border-color: #c62828;
    }

    .error-message {
      color: #c62828;
      font-size: 12px;
      margin-top: 5px;
    }

    .form-actions {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid #e0e0e0;
    }

    .btn-cancel, .btn-submit, .btn-delete-confirm {
      padding: 10px 20px;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.2s;
    }

    .btn-cancel {
      background: var(--color-gray-200);
      color: var(--color-primary);
      border: 1px solid var(--color-gray-300);
    }

    .btn-cancel:hover {
      background: var(--color-gray-300);
    }

    .btn-submit {
      background: var(--color-primary);
      color: var(--color-gray-100);
      border: 1px solid var(--color-primary);
    }

    .btn-submit:hover:not(:disabled) {
      background: var(--color-primary-light);
      border-color: var(--color-primary-light);
    }

    .btn-submit:disabled {
      background: var(--color-gray-400);
      border-color: var(--color-gray-400);
      cursor: not-allowed;
    }

    .btn-delete-confirm {
      background: var(--color-primary);
      color: var(--color-gray-100);
      border: 1px solid var(--color-primary);
    }

    .btn-delete-confirm:hover:not(:disabled) {
      background: var(--color-primary-light);
      border-color: var(--color-primary-light);
    }

    .btn-delete-confirm:disabled {
      background: var(--color-gray-400);
      border-color: var(--color-gray-400);
      cursor: not-allowed;
    }

    .warning-text {
      color: #c62828;
      font-weight: 500;
      margin-top: 10px;
    }

    /* Icons */
    .icon-users::before { content: "👥"; }
    .icon-plus::before { content: "➕"; }
    .icon-error::before { content: "❌"; }
    .icon-empty::before { content: "📭"; }
    .icon-edit::before { content: "✏️"; }
    .icon-delete::before { content: "🗑️"; }
    .icon-close::before { content: "✕"; }
    .icon-upload::before { content: "UPLOAD"; }

    @media (max-width: 800px) {
      .import-controls {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class UserManagementComponent implements OnInit {
  private userService = inject(UserService);
  private formBuilder = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);

  // Signals for reactive state management
  users = signal<User[]>([]);
  isLoading = signal(false);
  error = signal<string | null>(null);
  showModal = signal(false);
  isEditMode = signal(false);
  isSubmitting = signal(false);
  showDeleteModal = signal(false);
  isDeleting = signal(false);
  isImporting = signal(false);
  selectedImportFiles = signal<File[]>([]);
  importResult = signal<BulkImportResult | null>(null);
  importError = signal<string | null>(null);
  userToDelete = signal<User | null>(null);
  currentEditingUser = signal<User | null>(null);
  searchTerm = '';
  bulkImportTarget = 'auto';

  userForm: FormGroup;

  constructor() {
    this.userForm = this.formBuilder.group({
      username: ['', [
        Validators.required,
        Validators.minLength(1),
        Validators.maxLength(50),
        Validators.pattern(/^[a-zA-Z0-9_]+$/),
        this.usernameUniquenessValidator.bind(this)
      ]],
      email: ['', [
        Validators.required, 
        Validators.email,
        this.emailUniquenessValidator.bind(this)
      ]],
      first_name: ['', [Validators.maxLength(50)]],
      last_name: ['', [Validators.maxLength(50)]],
      role: ['']
    });
  }

  ngOnInit() {
    // Check if user is admin
    const user = this.authService.getCurrentUser();
    if (user?.role !== 'admin') {
      // Redirect non-admin users to dashboard
      this.router.navigate(['/']);
      return;
    }

    // Subscribe to the service's users observable for real-time updates
    this.userService.users$.subscribe(users => {
      this.users.set(users);
    });
    
    // Load initial data
    this.loadUsers();
  }

  loadUsers() {
    this.isLoading.set(true);
    this.error.set(null);
    
    this.userService.getUsers().subscribe({
      next: (users) => {
        this.users.set(users);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load users');
        this.isLoading.set(false);
        console.error('Error loading users:', err);
      }
    });
  }

  filteredUsers(): User[] {
    if (!this.searchTerm.trim()) {
      return this.users();
    }
    
    const term = this.searchTerm.toLowerCase();
    return this.users().filter(user => 
      user.username.toLowerCase().includes(term) ||
      user.email.toLowerCase().includes(term) ||
      (user.full_name && user.full_name.toLowerCase().includes(term)) ||
      (user.first_name && user.first_name.toLowerCase().includes(term)) ||
      (user.last_name && user.last_name.toLowerCase().includes(term))
    );
  }

  openCreateModal() {
    this.isEditMode.set(false);
    this.userForm.reset();
    this.showModal.set(true);
  }

  openEditModal(user: User) {
    this.isEditMode.set(true);
    this.currentEditingUser.set(user);
    this.userForm.patchValue({
      username: user.username,
      email: user.email,
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      role: user.role || ''
    });
    // Trigger validation to check username and email uniqueness
    this.userForm.get('username')?.updateValueAndValidity();
    this.userForm.get('email')?.updateValueAndValidity();
    this.showModal.set(true);
  }

  closeModal() {
    this.showModal.set(false);
    this.userForm.reset();
    this.userForm.markAsUntouched();
    this.userForm.markAsPristine();
    this.isSubmitting.set(false);
    this.currentEditingUser.set(null);
    this.error.set(null);
  }

  onSubmit() {
    if (this.userForm.invalid) {
      this.markFormGroupTouched();
      return;
    }

    this.isSubmitting.set(true);
    const formData = this.userForm.value;

    if (this.isEditMode()) {
      const currentUser = this.currentEditingUser();
      if (currentUser?.id) {
        const updateData: UserUpdateRequest = {
          username: formData.username,
          email: formData.email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          role: formData.role
        };

        this.userService.updateUser(currentUser.id, updateData).subscribe({
          next: (updatedUser) => {
            if (updatedUser) {
              this.closeModal();
              // Service will automatically update the observable
            } else {
              this.error.set('Failed to update user');
            }
            this.isSubmitting.set(false);
          },
          error: (err) => {
            console.error('Error updating user:', err);
            // Extract specific error message from API response
            const errorMessage = err.error?.message || err.error?.error || 'Failed to update user';
            this.error.set(errorMessage);
            this.isSubmitting.set(false);
          }
        });
      } else {
        this.error.set('No user selected for editing');
        this.isSubmitting.set(false);
      }
    } else {
      const createData: UserCreateRequest = {
        username: formData.username,
        email: formData.email,
        first_name: formData.first_name,
        last_name: formData.last_name,
        role: formData.role
      };

        this.userService.createUser(createData).subscribe({
          next: (newUser) => {
            if (newUser) {
              this.closeModal();
              // Service will automatically update the observable
            } else {
              this.error.set('Failed to create user');
            }
            this.isSubmitting.set(false);
          },
          error: (err) => {
            console.error('Error creating user:', err);
            // Extract specific error message from API response
            const errorMessage = err.error?.message || err.error?.error || 'Failed to create user';
            this.error.set(errorMessage);
            this.isSubmitting.set(false);
          }
        });
    }
  }

  confirmDelete(user: User) {
    this.userToDelete.set(user);
    this.showDeleteModal.set(true);
  }

  cancelDelete() {
    this.showDeleteModal.set(false);
    this.userToDelete.set(null);
    this.isDeleting.set(false);
  }

  deleteUser() {
    const user = this.userToDelete();
    if (!user?.id) return;

    this.isDeleting.set(true);
    this.userService.deleteUser(user.id).subscribe({
      next: (success) => {
        if (success) {
          this.cancelDelete();
          // Service will automatically update the observable
        } else {
          this.error.set('Failed to delete user');
        }
        this.isDeleting.set(false);
      },
      error: (err) => {
        console.error('Error deleting user:', err);
        // Extract specific error message from API response
        const errorMessage = err.error?.message || err.error?.error || 'Failed to delete user';
        this.error.set(errorMessage);
        this.isDeleting.set(false);
      }
    });
  }

  onBulkImportFilesSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    this.selectedImportFiles.set(Array.from(input.files || []));
    this.importResult.set(null);
    this.importError.set(null);
  }

  runBulkImport() {
    const files = this.selectedImportFiles();
    if (!files.length) {
      this.importError.set('Select at least one Excel file');
      return;
    }

    this.isImporting.set(true);
    this.importError.set(null);
    this.importResult.set(null);

    this.userService.bulkImport(this.bulkImportTarget, files).subscribe({
      next: (result) => {
        this.importResult.set(result);
        this.isImporting.set(false);
      },
      error: (err) => {
        console.error('Bulk import failed:', err);
        this.importError.set(err.error?.message || err.message || 'Bulk import failed');
        this.isImporting.set(false);
      }
    });
  }

  showDeleteModalSignal(): boolean {
    return this.showDeleteModal();
  }

  private markFormGroupTouched() {
    Object.keys(this.userForm.controls).forEach(key => {
      const control = this.userForm.get(key);
      control?.markAsTouched();
    });
  }

  private usernameUniquenessValidator(control: any) {
    if (!control.value) {
      return null;
    }

    const username = control.value.toLowerCase();
    const currentUsers = this.users();
    const currentEditingUser = this.currentEditingUser();

    // Check if username already exists (excluding current user in edit mode)
    const existingUser = currentUsers.find(user => 
      user.username.toLowerCase() === username && 
      user.id !== currentEditingUser?.id
    );

    return existingUser ? { usernameExists: true } : null;
  }

  private emailUniquenessValidator(control: any) {
    if (!control.value) {
      return null;
    }

    const email = control.value.toLowerCase();
    const currentUsers = this.users();
    const currentEditingUser = this.currentEditingUser();

    // Check if email already exists (excluding current user in edit mode)
    const existingUser = currentUsers.find(user => 
      user.email.toLowerCase() === email && 
      user.id !== currentEditingUser?.id
    );

    return existingUser ? { emailExists: true } : null;
  }
}
