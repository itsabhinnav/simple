import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { DesignTicketService, DesignTicket } from '../../services/design-ticket.service';

@Component({
  selector: 'app-design-ticket-management',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="design-ticket-management-container">
      <!-- Header -->
      <header class="management-header">
        <div class="header-left">
          <nav class="breadcrumb">
            <a routerLink="/" class="breadcrumb-link">
              <i class="icon-database">📊</i>
              Dashboard
            </a>
            <span class="breadcrumb-separator">›</span>
            <span class="breadcrumb-current">Designs</span>
          </nav>
          <h1 class="page-title">
            <i class="icon-design">🎨</i>
            Design Management
          </h1>
        </div>
        <div class="header-right">
          <button 
            class="add-btn" 
            routerLink="/design-tickets/create"
            [disabled]="isLoading()">
            <i class="icon-plus">➕</i>
            Add New Design
          </button>
          <div class="view-toggle">
            <button class="view-btn" [class.active]="currentView() === 'grid'" (click)="currentView.set('grid')" title="Grid View">
              <i class="icon-grid">⊞</i>
            </button>
            <button class="view-btn" [class.active]="currentView() === 'table'" (click)="currentView.set('table')" title="Table View">
              <i class="icon-table">☰</i>
            </button>
          </div>
        </div>
      </header>

      <!-- Loading State -->
      <div *ngIf="isLoading()" class="loading-container">
        <div class="spinner"></div>
        <p>Loading designs...</p>
      </div>

      <!-- Error State -->
      <div *ngIf="error()" class="error-container">
        <i class="icon-error">❌</i>
        <p>{{ error() }}</p>
        <button (click)="loadDesignTickets()" class="retry-btn">Retry</button>
      </div>

      <!-- Designs Board -->
      <div *ngIf="!isLoading() && !error()" class="board-container">
        <div class="board-header">
          <h3>Designs ({{ filteredDesignTickets().length }})</h3>
        </div>
        
        <!-- Empty State -->
        <div *ngIf="filteredDesignTickets().length === 0" class="empty-state">
          <div class="empty-icon">🎨</div>
          <h2>No Designs Found</h2>
          <p class="empty-description">Designs help you document system designs, diagrams, and visual specifications.</p>
          <button class="empty-action-btn" routerLink="/design-tickets/create">
            <span>➕</span>
            Create Your First Design
          </button>
        </div>

        <!-- Table View -->
        <div *ngIf="filteredDesignTickets().length > 0 && currentView() === 'table'" class="table-view-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Design ID</th>
                <th>Title</th>
                <th>Design Type</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Linked Requirement</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let dt of filteredDesignTickets()" (click)="navigateToDetail(dt.design_ticket_id)" style="cursor: pointer;">
                <td><strong>{{ dt.design_ticket_id }}</strong></td>
                <td>{{ dt.title }}</td>
                <td><span class="type-badge">{{ dt.design_type || '-' }}</span></td>
                <td><span class="priority-badge" [class]="getPriorityClass(dt.priority)">{{ dt.priority || 'P3' }}</span></td>
                <td><span class="status-badge" [class]="getStatusClass(dt.status)">{{ dt.status || 'Draft' }}</span></td>
                <td>{{ dt.requirement_id || '-' }}</td>
                <td (click)="$event.stopPropagation()">
                  <button class="btn-edit" (click)="openEditModal(dt)">Edit</button>
                  <button class="btn-delete" (click)="confirmDelete(dt)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Grid View -->
        <div *ngIf="filteredDesignTickets().length > 0 && currentView() === 'grid'" class="requirements-grid">
          <div *ngFor="let dt of filteredDesignTickets()" class="requirement-card" (click)="navigateToDetail(dt.design_ticket_id)">
            <div class="card-header">
              <span class="req-id">{{ dt.design_ticket_id }}</span>
              <span class="status-badge" [class]="getStatusClass(dt.status)">
                {{ dt.status || 'Draft' }}
              </span>
            </div>
            <h3 class="card-title">{{ dt.title }}</h3>
            <p class="card-description" *ngIf="dt.description">{{ dt.description }}</p>
            
            <div class="card-footer">
              <span class="type-badge" *ngIf="dt.design_type">{{ dt.design_type }}</span>
              <span class="priority-badge" [class]="getPriorityClass(dt.priority)">
                {{ dt.priority || 'P3' }}
              </span>
            </div>
            <div class="card-actions" (click)="$event.stopPropagation()">
              <button class="btn-edit" (click)="openEditModal(dt)" title="Edit">✏️</button>
              <button class="btn-delete" (click)="confirmDelete(dt)" title="Delete">🗑️</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .design-ticket-management-container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 20px;
    }

    .management-header {
      background-color: white;
      border: 1px solid #dadce0;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .header-left {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .view-toggle {
      display: flex;
      gap: 4px;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 4px;
    }

    .view-btn {
      padding: 8px;
      border: none;
      background: transparent;
      cursor: pointer;
      border-radius: 6px;
      color: #5f6368;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      font-size: 16px;
    }

    .view-btn:hover {
      background: #f5f5f5;
      color: #202124;
    }

    .view-btn.active {
      background: #1a73e8;
      color: white;
    }

    .breadcrumb {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }

    .breadcrumb-link {
      color: #5f6368;
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 5px;
      transition: color 0.2s;
      font-size: 14px;
    }

    .breadcrumb-link:hover {
      color: #202124;
    }

    .breadcrumb-separator {
      color: #5f6368;
    }

    .breadcrumb-current {
      color: #202124;
      font-weight: 500;
      font-size: 14px;
    }

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .add-btn {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px;
      background: #1a73e8;
      color: white;
      border: none;
      border-radius: 24px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
      text-decoration: none;
    }

    .add-btn:hover:not(:disabled) {
      background: #1557b0;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    }

    .add-btn:disabled {
      background: #dadce0;
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
      border-top: 4px solid #1a73e8;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .board-container {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 24px;
    }

    .board-header h3 {
      margin: 0 0 16px 0;
      color: #333;
    }

    .empty-state {
      text-align: center;
      padding: 80px 40px;
      color: #666;
    }

    .empty-icon {
      font-size: 80px;
      margin-bottom: 24px;
      opacity: 0.5;
    }

    .empty-state h2 {
      margin: 0 0 12px 0;
      font-size: 24px;
      font-weight: 600;
      color: #202124;
    }

    .empty-description {
      margin: 0 auto 32px;
      font-size: 16px;
      color: #5f6368;
      max-width: 500px;
      line-height: 1.6;
    }

    .empty-action-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 12px 24px;
      background: #1a73e8;
      color: white;
      border: none;
      border-radius: 24px;
      font-size: 15px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      box-shadow: 0 2px 4px rgba(26, 115, 232, 0.2);
    }

    .empty-action-btn:hover {
      background: #1557b0;
      box-shadow: 0 4px 8px rgba(26, 115, 232, 0.3);
      transform: translateY(-1px);
    }

    .empty-action-btn span {
      font-size: 18px;
    }

    .table-view-container {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      overflow: hidden;
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
    }

    .data-table td {
      padding: 12px 16px;
      border-bottom: 1px solid #e0e0e0;
    }

    .data-table tbody tr:hover {
      background: #f9f9f9;
    }

    .data-table tbody tr:last-child td {
      border-bottom: none;
    }

    .type-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      display: inline-block;
    }

    .priority-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }

    .priority-p1 { background: #ffebee; color: #c62828; }
    .priority-p2 { background: #fff3e0; color: #ef6c00; }
    .priority-p3 { background: #e8f5e8; color: #2e7d32; }

    .status-badge {
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }

    .status-draft { background: #f5f5f5; color: #757575; }
    .status-approved { background: #e8f5e8; color: #2e7d32; }
    .status-review { background: #f3e5f5; color: #7b1fa2; }
    .status-default { background: #fafafa; color: #757575; }

    .btn-edit, .btn-delete {
      padding: 6px 12px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.2s;
      margin-right: 4px;
    }

    .btn-edit {
      background: #e3f2fd;
      color: #1976d2;
    }

    .btn-edit:hover {
      background: #bbdefb;
    }

    .btn-delete {
      background: #ffebee;
      color: #c62828;
    }

    .btn-delete:hover {
      background: #ffcdd2;
    }

    .requirements-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }

    .requirement-card {
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 16px;
      transition: all 0.2s;
      cursor: pointer;
    }

    .requirement-card:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .req-id {
      font-weight: 600;
      color: #1a73e8;
      font-size: 13px;
    }

    .card-title {
      margin: 8px 0;
      font-size: 16px;
      font-weight: 600;
      color: #333;
    }

    .card-description {
      font-size: 14px;
      color: #666;
      margin: 8px 0;
      line-height: 1.5;
    }

    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid #f0f0f0;
    }

    .card-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid #f0f0f0;
    }

    .retry-btn {
      background: #1a73e8;
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 24px;
      cursor: pointer;
      font-weight: 500;
      margin-top: 15px;
      transition: all 0.2s;
    }

    .retry-btn:hover {
      background: #1557b0;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    }

    .icon-database::before { content: "📊"; }
    .icon-plus::before { content: "➕"; }
    .icon-error::before { content: "❌"; }
    .icon-empty::before { content: "📭"; }
    .icon-edit::before { content: "✏️"; }
    .icon-delete::before { content: "🗑️"; }
  `]
})
export class DesignTicketManagementComponent implements OnInit {
  private designTicketService = inject(DesignTicketService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  // Signals for reactive state management
  designTickets = signal<DesignTicket[]>([]);
  isLoading = signal(false);
  error = signal<string | null>(null);
  currentView = signal<'grid' | 'table'>('table');
  searchTerm = signal('');
  
  // Computed signal for filtered design tickets
  filteredDesignTickets = computed(() => {
    let filtered = this.designTickets();
    
    // Text search
    if (this.searchTerm().trim()) {
      const term = this.searchTerm().toLowerCase();
      filtered = filtered.filter(dt =>
        dt.design_ticket_id?.toLowerCase().includes(term) ||
        dt.title?.toLowerCase().includes(term) ||
        dt.description?.toLowerCase().includes(term) ||
        dt.design_type?.toLowerCase().includes(term)
      );
    }
    
    return filtered;
  });

  ngOnInit() {
    this.loadDesignTickets();
  }

  loadDesignTickets() {
    this.isLoading.set(true);
    this.error.set(null);
    
    this.designTicketService.getDesignTickets().subscribe({
      next: (designTickets) => {
        this.designTickets.set(designTickets);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load designs');
        this.isLoading.set(false);
        console.error('Error loading design tickets:', err);
      }
    });
  }

  navigateToDetail(ticketId: string) {
    this.router.navigate(['/design-tickets', ticketId]);
  }

  openEditModal(dt: DesignTicket) {
    this.router.navigate(['/design-tickets/edit', dt.design_ticket_id]);
  }

  confirmDelete(dt: DesignTicket) {
    if (confirm(`Are you sure you want to delete ${dt.design_ticket_id}?`)) {
      this.deleteDesignTicket(dt.id!);
    }
  }

  deleteDesignTicket(id: number) {
    this.designTicketService.deleteDesignTicket(id).subscribe({
      next: (success) => {
        if (success) {
          this.loadDesignTickets();
        } else {
          alert('Failed to delete design');
        }
      },
      error: (err) => {
        alert('Error deleting design');
        console.error(err);
      }
    });
  }

  getPriorityClass(priority: string): string {
    const p = priority?.toUpperCase() || 'P3';
    if (p.startsWith('P1')) return 'priority-p1';
    if (p.startsWith('P2')) return 'priority-p2';
    return 'priority-p3';
  }

  getStatusClass(status: string): string {
    const s = status?.toLowerCase() || 'draft';
    if (s === 'approved' || s === 'completed') return 'status-approved';
    if (s === 'review') return 'status-review';
    if (s === 'draft') return 'status-draft';
    return 'status-default';
  }
}
