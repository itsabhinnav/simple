import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { SpecService, Spec } from '../services/spec.service';

@Component({
  selector: 'app-spec-management',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './spec-management.component.html',
  styleUrls: ['./spec-management.component.scss']
})
export class SpecManagementComponent implements OnInit {
  private specService = inject(SpecService);
  private fb = inject(FormBuilder);

  specs = signal<Spec[]>([]);
  isSubmitting = signal(false);
  isImporting = signal(false);
  showCreateForm = signal(false);
  importError = signal<string | null>(null);

  totalSpecs = computed(() => this.specs().length);

  form: FormGroup = this.fb.group({
    spec_id: ['', [Validators.required]],
    title: ['', [Validators.required]],
    description: [''],
    category: [''],
    version: [''],
    status: ['Draft']
  });

  ngOnInit() {
    this.reload();
  }

  reload() {
    this.specService.getSpecs().subscribe(list => this.specs.set(list));
  }

  toggleCreateForm() {
    this.showCreateForm.update(v => !v);
  }

  onCreate() {
    if (this.form.invalid) return;
    this.isSubmitting.set(true);
    this.specService.createSpec(this.form.value as Spec).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.form.reset({ status: 'Draft' });
        this.showCreateForm.set(false);
        this.reload();
      },
      error: () => { this.isSubmitting.set(false); }
    });
  }

  onCancelCreate() {
    this.form.reset({ status: 'Draft' });
    this.showCreateForm.set(false);
  }

  onFileSelected(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.importError.set(null);
    this.isImporting.set(true);
    this.specService.importSpecs(file).subscribe({
      next: () => { this.isImporting.set(false); this.reload(); input.value = ''; },
      error: (err) => {
        this.isImporting.set(false);
        this.importError.set('Import failed. Please verify the file format.');
        console.error('Import failed', err);
      }
    });
  }

  statusClass(status?: string): string {
    const s = (status || '').toLowerCase();
    if (s === 'approved') return 'status-approved';
    if (s === 'review' || s === 'in review') return 'status-review';
    if (s === 'archived') return 'status-archived';
    return 'status-draft';
  }
}
