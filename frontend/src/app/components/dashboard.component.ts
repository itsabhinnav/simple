import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { DatabaseService } from '../services/database.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="dashboard-container">
      <!-- Header -->
      <header class="dashboard-header">
        <h1 class="app-title">
          <i class="icon-database"></i>
          Sakura Database Tables
        </h1>
        <div class="header-actions">
          <nav class="nav-menu">
            <a routerLink="/users" class="nav-link">
              <i class="icon-users"></i>
              User Management
            </a>
            <a routerLink="/test-cases" class="nav-link">
              <i class="icon-test-cases"></i>
              Test Case Management
            </a>
          </nav>
          <button 
            class="refresh-btn" 
            (click)="loadTables()"
            [disabled]="isLoading()">
            <i class="icon-refresh"></i>
            Refresh Tables
          </button>
        </div>
      </header>

      <!-- Loading State -->
      <div *ngIf="isLoading()" class="loading-container">
        <div class="spinner"></div>
        <p>Loading tables...</p>
        <p>Debug: isLoading={{isLoading()}}, tables.length={{tables().length}}</p>
        <p>Debug: tables={{tables() | json}}</p>
      </div>

      <!-- Error State -->
      <div *ngIf="error()" class="error-container">
        <i class="icon-error"></i>
        <p>{{ error() }}</p>
        <button (click)="loadTables()" class="retry-btn">Retry</button>
      </div>

      <!-- Tables Display -->
      <div *ngIf="!isLoading() && !error() && tables().length > 0" class="tables-container">
        <div *ngFor="let table of tables()" class="table-section">
          <h2 class="table-title">{{ table.name }}</h2>
          <div class="table-info">
            <span class="table-count">{{ table.count }} rows</span>
          </div>
          
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th *ngFor="let column of table.columns">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let row of table.data">
                  <td *ngFor="let column of table.columns">{{ row[column] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div *ngIf="!isLoading() && !error() && tables().length === 0" class="empty-state">
        <i class="icon-empty"></i>
        <h3>No Tables Found</h3>
        <p>No tables found in the database.</p>
        <button (click)="loadTables()" class="retry-btn">Refresh</button>
      </div>

    </div>
  `,
  styles: [`
    .dashboard-container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 20px;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    .dashboard-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 20px;
      border-radius: 12px;
      margin-bottom: 30px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 20px;
    }

    .nav-menu {
      display: flex;
      gap: 15px;
    }

    .nav-link {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: rgba(255, 255, 255, 0.1);
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
      border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .nav-link:hover {
      background: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }

    .nav-link.router-link-active {
      background: rgba(255, 255, 255, 0.3);
      border-color: rgba(255, 255, 255, 0.4);
    }

    .app-title {
      margin: 0;
      font-size: 2rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .refresh-btn {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px;
      background: rgba(255, 255, 255, 0.2);
      color: white;
      border: 1px solid rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }

    .refresh-btn:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.3);
    }

    .refresh-btn:disabled {
      background: rgba(255, 255, 255, 0.1);
      cursor: not-allowed;
    }

    .loading-container, .error-container {
      text-align: center;
      padding: 60px 20px;
    }

    .spinner {
      width: 40px;
      height: 40px;
      border: 4px solid #f3f3f3;
      border-top: 4px solid #2196f3;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .tables-container {
      display: flex;
      flex-direction: column;
      gap: 30px;
    }

    .table-section {
      background: white;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    }

    .table-title {
      margin: 0 0 10px 0;
      font-size: 1.5rem;
      font-weight: 600;
      color: #333;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .table-info {
      margin-bottom: 20px;
    }

    .table-count {
      background: #e3f2fd;
      color: #1976d2;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 500;
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

    /* Icons */
    .icon-database::before { content: "🗄️"; }
    .icon-refresh::before { content: "🔄"; }
    .icon-error::before { content: "❌"; }
    .icon-empty::before { content: "📭"; }
    .icon-users::before { content: "👥"; }
    .icon-test-cases::before { content: "🧪"; }
  `]
})
export class DashboardComponent implements OnInit {
  private databaseService = inject(DatabaseService);

  // Properties using signals for better change detection
  tables = signal<any[]>([]);
  isLoading = signal(false);
  error = signal<string | null>(null);

  ngOnInit() {
    this.loadTables();
  }

  loadTables() {
    this.isLoading.set(true);
    this.error.set(null);
    console.log('Starting to load tables...');

    // Load all tables from the database
    const tableQueries = [
      { name: 'requirements', query: 'SELECT * FROM requirements LIMIT 10' },
      { name: 'test_cases', query: 'SELECT * FROM test_cases LIMIT 10' }
    ];

    let completedQueries = 0;
    const tables: any[] = [];

    tableQueries.forEach(tableQuery => {
      console.log(`Loading table: ${tableQuery.name}`);
      this.databaseService.executeQuery('sakura_db', tableQuery.query, 'default').subscribe({
        next: (result) => {
          console.log(`Successfully loaded ${tableQuery.name}:`, result);
          const tableData = {
            name: tableQuery.name,
            data: result?.data?.data || [],
            columns: result?.data?.columns || [],
            count: result?.data?.row_count || 0
          };
          
          if (tableData.count > 0) {
            tables.push(tableData);
          }
          
          completedQueries++;
          console.log(`Completed ${completedQueries}/${tableQueries.length} queries`);
          if (completedQueries === tableQueries.length) {
            this.tables.set(tables);
            this.isLoading.set(false);
            console.log('All tables loaded:', this.tables());
          }
        },
        error: (err) => {
          console.error(`Failed to load ${tableQuery.name}:`, err);
          completedQueries++;
          if (completedQueries === tableQueries.length) {
            this.tables.set(tables);
            this.isLoading.set(false);
            console.log('All queries completed with errors:', this.tables());
          }
        }
      });
    });
  }
}
