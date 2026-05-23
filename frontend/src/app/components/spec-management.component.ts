import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { SpecService, Spec } from '../services/spec.service';

@Component({
  selector: 'app-spec-management',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
  <div class="detail-container">
    <header class="detail-header">
      <div class="header-left">
        <nav class="breadcrumb">
          <a routerLink="/" class="breadcrumb-link"><i class="icon-database"></i> Dashboard</a>
          <span class="breadcrumb-separator">›</span>
          <span class="breadcrumb-current">Specifications</span>
        </nav>
        <h1 class="page-title"><i class="icon-requirements"></i> Specifications</h1>
      </div>
      <div class="header-actions">
        <label class="btn">
          <input type="file" (change)="onFileSelected($event)" hidden />
          Import
        </label>
      </div>
    </header>

    <div class="detail-content">
      <div class="detail-card" style="margin-bottom:16px;">
        <div class="card-header"><div class="header-top"><div class="title-group">
          <h3 class="section-title">Create Specification</h3>
        </div></div></div>
        <div class="card-body">
          <form [formGroup]="form" (ngSubmit)="onCreate()">
            <div class="detail-meta">
              <div class="meta-item"><span class="meta-label">Spec ID</span>
                <input class="meta-value editable-input" formControlName="spec_id" placeholder="SPEC_0001" />
              </div>
              <div class="meta-item"><span class="meta-label">Title</span>
                <input class="meta-value editable-input" formControlName="title" placeholder="Title" />
              </div>
              <div class="meta-item"><span class="meta-label">Category</span>
                <input class="meta-value editable-input" formControlName="category" placeholder="SRS/PRD" />
              </div>
              <div class="meta-item"><span class="meta-label">Version</span>
                <input class="meta-value editable-input" formControlName="version" placeholder="1.0" />
              </div>
              <div class="meta-item"><span class="meta-label">Status</span>
                <input class="meta-value editable-input" formControlName="status" placeholder="Draft/Approved" />
              </div>
            </div>
            <div class="detail-section">
              <textarea class="section-content editable-textarea" formControlName="description" placeholder="Description"></textarea>
            </div>
            <div class="form-actions"><button class="btn-submit" type="submit" [disabled]="form.invalid || isSubmitting()">{{ isSubmitting() ? 'Saving...' : 'Create Spec' }}</button></div>
          </form>
        </div>
      </div>

      <div class="detail-card">
        <div class="card-header"><div class="header-top"><div class="title-group">
          <h3 class="section-title">All Specifications</h3>
        </div></div></div>
        <div class="card-body">
          <div *ngFor="let s of specs()" class="linked-item">
            <span class="linked-id">{{ s.spec_id }}</span>
            <span class="linked-title">{{ s.title }}</span>
            <span class="linked-title" *ngIf="s.version">v{{ s.version }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  `,
  styleUrls: ['./requirement-detail.component.scss']
})
export class SpecManagementComponent implements OnInit {
  private specService = inject(SpecService);
  private fb = inject(FormBuilder);

  specs = signal<Spec[]>([]);
  isSubmitting = signal(false);

  form: FormGroup = this.fb.group({
    spec_id: ['', [Validators.required]],
    title: ['', [Validators.required]],
    description: [''],
    category: [''],
    version: [''],
    status: ['']
  });

  ngOnInit() {
    this.reload();
  }

  reload() {
    this.specService.getSpecs().subscribe(list => this.specs.set(list));
  }

  onCreate() {
    if (this.form.invalid) return;
    this.isSubmitting.set(true);
    this.specService.createSpec(this.form.value as Spec).subscribe({
      next: () => { this.isSubmitting.set(false); this.form.reset(); this.reload(); },
      error: () => { this.isSubmitting.set(false); }
    });
  }

  onFileSelected(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.specService.importSpecs(file).subscribe({
      next: () => this.reload(),
      error: (err) => console.error('Import failed', err)
    });
  }
}








