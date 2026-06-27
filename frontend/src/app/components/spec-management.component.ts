import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { SpecService, Spec, SpecCreatePayload, SpecProjectSummary } from '../services/spec.service';

type AddMode = 'new' | 'version';
type PageView = 'projects' | 'browse';

@Component({
  selector: 'app-spec-management',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './spec-management.component.html',
  styleUrls: ['./spec-management.component.scss']
})
export class SpecManagementComponent implements OnInit {
  private specService = inject(SpecService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private fb = inject(FormBuilder);

  projects = signal<SpecProjectSummary[]>([]);
  allSpecs = signal<Spec[]>([]);
  existingVersions = signal<Spec[]>([]);
  knownSpecIds = signal<string[]>([]);
  isSubmitting = signal(false);
  showAddForm = signal(false);
  addMode = signal<AddMode>('new');
  pageView = signal<PageView>('projects');
  submitError = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  searchTerm = signal('');
  selectedFile = signal<File | null>(null);
  fileInputMode = signal<'upload' | 'link'>('upload');
  projectFilter = signal('');

  stats = computed(() => {
    const projects = this.projects();
    return {
      projects: projects.length,
      documents: projects.reduce((n, p) => n + (p.spec_families || 0), 0),
      versions: projects.reduce((n, p) => n + (p.spec_count || 0), 0),
    };
  });

  recentSpecs = computed(() => this.allSpecs().slice(0, 6));

  filteredSpecs = computed(() => {
    const project = this.projectFilter();
    const term = this.searchTerm().trim().toLowerCase();
    return this.allSpecs().filter(s => {
      if (project) {
        if (project === 'Unassigned') {
          if (s.project?.trim()) return false;
        } else if ((s.project || '') !== project) {
          return false;
        }
      }
      if (!term) return true;
      return (
        s.spec_id.toLowerCase().includes(term) ||
        s.title.toLowerCase().includes(term) ||
        (s.tags || '').toLowerCase().includes(term) ||
        (s.project || '').toLowerCase().includes(term)
      );
    });
  });

  form: FormGroup = this.fb.group({
    spec_id: ['', [Validators.required]],
    title: ['', [Validators.required]],
    project: ['', [Validators.required]],
    tags: [''],
    category: [''],
    version: ['', [Validators.required]],
    status: ['Draft'],
    source_url: ['']
  });

  ngOnInit() {
    this.reloadProjects();
    this.reloadAllSpecs();
    this.route.queryParamMap.subscribe(params => {
      if (params.get('view') === 'browse') this.pageView.set('browse');
      const shouldOpenAdd = params.get('add') === '1' || params.get('mode') === 'version';
      if (!shouldOpenAdd) return;
      const mode = params.get('mode') === 'version' ? 'version' : 'new';
      this.addMode.set(mode);
      this.showAddForm.set(true);
      this.form.patchValue({
        project: params.get('project') || '',
        spec_id: params.get('spec_id') || '',
        title: params.get('title') || '',
        category: params.get('category') || '',
      });
      if (mode === 'version') this.refreshExistingVersions();
    });
  }

  reloadProjects() {
    this.specService.getProjects().subscribe(list => this.projects.set(list));
  }

  reloadAllSpecs() {
    this.specService.getSpecs().subscribe(list => {
      this.allSpecs.set(list);
      this.knownSpecIds.set(Array.from(new Set(list.map(s => s.spec_id))).sort());
    });
  }

  setPageView(view: PageView) {
    this.pageView.set(view);
  }

  onSearchInput(value: string) {
    this.searchTerm.set(value);
  }

  onProjectFilterChange(value: string) {
    this.projectFilter.set(value);
  }

  openProject(project: string, event?: Event) {
    event?.stopPropagation();
    this.router.navigate(['/specs/project', encodeURIComponent(project || 'Unassigned')]);
  }

  openSpecRow(spec: Spec, event?: Event) {
    if ((event?.target as HTMLElement)?.closest('a, button')) return;
    const project = spec.project?.trim() || 'Unassigned';
    this.router.navigate(['/specs/project', encodeURIComponent(project)], {
      queryParams: { spec_id: spec.spec_id, version: spec.version || undefined },
    });
  }

  openAddForm(mode: AddMode = 'new', project?: string) {
    this.addMode.set(mode);
    this.showAddForm.set(true);
    this.submitError.set(null);
    this.successMessage.set(null);
    if (project) this.form.patchValue({ project: project === 'Unassigned' ? '' : project });
    if (mode === 'new') {
      this.form.patchValue({ spec_id: '', title: '', version: '', category: '', tags: '' });
    }
  }

  setAddMode(mode: AddMode) {
    this.addMode.set(mode);
    this.submitError.set(null);
    this.existingVersions.set([]);
    if (mode === 'new') {
      this.form.patchValue({ spec_id: '', title: '', version: '', category: '', tags: '' });
    } else {
      this.refreshExistingVersions();
    }
  }

  toggleAddForm() {
    if (this.showAddForm()) {
      this.onCancelAdd();
    } else {
      this.openAddForm('new');
    }
  }

  onProjectOrSpecIdChange() {
    if (this.addMode() === 'version') this.refreshExistingVersions();
  }

  refreshExistingVersions() {
    const project = (this.form.value.project || '').trim();
    const specId = (this.form.value.spec_id || '').trim();
    if (!project || !specId) {
      this.existingVersions.set([]);
      return;
    }
    this.specService.getSpecVersions(specId, project).subscribe(versions => {
      this.existingVersions.set(versions);
      if (!versions.length) return;
      const latest = versions[0];
      if (!this.form.value.title) {
        this.form.patchValue({ title: latest.title, category: latest.category || '' });
      }
      if (!this.form.value.version) {
        this.form.patchValue({ version: this.suggestNextVersion(versions.map(v => v.version || '')) });
      }
    });
  }

  suggestNextVersion(existing: string[]): string {
    const cleaned = existing.map(v => v.trim()).filter(Boolean);
    if (!cleaned.length) return '1.0';
    const last = cleaned[0];
    const semver = last.match(/^(\d+)\.(\d+)(?:\.(\d+))?$/);
    if (semver) {
      const major = parseInt(semver[1], 10);
      const minor = parseInt(semver[2], 10);
      const patch = semver[3] ? parseInt(semver[3], 10) : null;
      if (patch !== null) return `${major}.${minor}.${patch + 1}`;
      return `${major}.${minor + 1}`;
    }
    const numeric = parseFloat(last);
    if (!Number.isNaN(numeric)) return String(numeric + 1);
    return `${last}-rev2`;
  }

  setFileMode(mode: 'upload' | 'link') {
    this.fileInputMode.set(mode);
    this.selectedFile.set(null);
    this.form.patchValue({ source_url: '' });
  }

  onSpecFileSelected(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.length) return;
    this.selectedFile.set(input.files[0]);
    this.fileInputMode.set('upload');
  }

  onAddSpec() {
    if (this.form.invalid) return;
    const docMode = this.fileInputMode();
    const file = docMode === 'upload' ? this.selectedFile() : null;
    const sourceUrl = (this.form.value.source_url || '').trim();
    if (docMode === 'upload' && !file) {
      this.submitError.set('Upload a spec file or switch to SharePoint / link.');
      return;
    }
    if (docMode === 'link' && !sourceUrl) {
      this.submitError.set('Paste a SharePoint or document link, or switch to file upload.');
      return;
    }

    this.submitError.set(null);
    this.isSubmitting.set(true);
    const payload: SpecCreatePayload = {
      spec_id: this.form.value.spec_id,
      title: this.form.value.title,
      project: this.form.value.project,
      tags: this.form.value.tags,
      category: this.form.value.category,
      version: this.form.value.version,
      status: this.form.value.status,
      source_url: docMode === 'link' ? sourceUrl : undefined
    };

    this.specService.createSpec(payload, file || undefined).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        const project = payload.project?.trim();
        this.resetForm();
        this.showAddForm.set(false);
        this.reloadProjects();
        this.reloadAllSpecs();
        if (project) {
          this.router.navigate(['/specs/project', encodeURIComponent(project)], {
            queryParams: { spec_id: payload.spec_id, version: payload.version },
          });
        } else {
          this.successMessage.set(`Added ${payload.spec_id} v${payload.version}.`);
        }
      },
      error: (err) => {
        this.isSubmitting.set(false);
        this.submitError.set(err?.message || 'Failed to add spec. Check the form and try again.');
      }
    });
  }

  onCancelAdd() {
    this.resetForm();
    this.showAddForm.set(false);
    this.router.navigate([], { queryParams: { add: null, mode: null, project: null, spec_id: null, title: null, category: null }, queryParamsHandling: 'merge' });
  }

  downloadSpec(spec: Spec, event?: Event) {
    event?.stopPropagation();
    if (!spec.id) return;
    this.specService.downloadSpecFile(spec.id, spec.file_name);
  }

  tagList(tags?: string): string[] {
    if (!tags?.trim()) return [];
    return tags.split(',').map(t => t.trim()).filter(Boolean);
  }

  statusClass(status?: string): string {
    return (status || '').toLowerCase() === 'official' ? 'status-official' : 'status-draft';
  }

  formatDate(value?: string): string {
    if (!value) return '—';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
  }

  private resetForm() {
    this.form.reset({ status: 'Draft' });
    this.addMode.set('new');
    this.existingVersions.set([]);
    this.selectedFile.set(null);
    this.fileInputMode.set('upload');
    this.submitError.set(null);
  }
}
