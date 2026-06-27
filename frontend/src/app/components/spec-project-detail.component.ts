import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { SpecService, Spec } from '../services/spec.service';

export interface SpecFamilyGroup {
  spec_id: string;
  title: string;
  versions: Spec[];
  latest: Spec;
}

@Component({
  selector: 'app-spec-project-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './spec-project-detail.component.html',
  styleUrls: ['./spec-project-detail.component.scss']
})
export class SpecProjectDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private specService = inject(SpecService);

  projectName = signal('');
  specs = signal<Spec[]>([]);
  searchTerm = signal('');
  expandedFamilyId = signal<string | null>(null);
  selectedVersion = signal<Spec | null>(null);

  groupedSpecs = computed<SpecFamilyGroup[]>(() => {
    const term = this.searchTerm().trim().toLowerCase();
    const filtered = this.specs().filter(s => {
      if (!term) return true;
      return (
        s.spec_id.toLowerCase().includes(term) ||
        s.title.toLowerCase().includes(term) ||
        (s.tags || '').toLowerCase().includes(term) ||
        (s.version || '').toLowerCase().includes(term)
      );
    });
    const map = new Map<string, SpecFamilyGroup>();
    for (const spec of filtered) {
      if (!map.has(spec.spec_id)) {
        map.set(spec.spec_id, { spec_id: spec.spec_id, title: spec.title, versions: [], latest: spec });
      }
      map.get(spec.spec_id)!.versions.push(spec);
    }
    for (const group of map.values()) {
      group.versions.sort((a, b) => (b.version || '').localeCompare(a.version || '', undefined, { numeric: true }));
      group.latest = group.versions[0];
    }
    return Array.from(map.values()).sort((a, b) => a.spec_id.localeCompare(b.spec_id));
  });

  totalVersions = computed(() => this.specs().length);

  ngOnInit() {
    this.route.paramMap.subscribe(() => {
      const project = decodeURIComponent(this.route.snapshot.paramMap.get('project') || 'Unassigned');
      this.projectName.set(project === 'Unassigned' ? '' : project);
      this.reload();
    });
    this.route.queryParamMap.subscribe(() => this.applyDeepLink());
  }

  reload() {
    const project = this.projectName();
    this.specService.getSpecs(undefined, project || 'Unassigned').subscribe(list => {
      this.specs.set(list);
      this.applyDeepLink(list);
    });
  }

  private applyDeepLink(list = this.specs()) {
    const specId = this.route.snapshot.queryParamMap.get('spec_id');
    const version = this.route.snapshot.queryParamMap.get('version');
    if (!specId) return;

    this.expandedFamilyId.set(specId);
    if (version) {
      const match = list.find(s => s.spec_id === specId && (s.version || '') === version);
      if (match) this.selectedVersion.set(match);
    } else {
      const family = list.filter(s => s.spec_id === specId);
      if (family.length) this.selectedVersion.set(family[0]);
    }
  }

  isExpanded(family: SpecFamilyGroup): boolean {
    const open = this.expandedFamilyId();
    if (open) return open === family.spec_id;
    return this.groupedSpecs().length === 1;
  }

  toggleFamily(family: SpecFamilyGroup) {
    const next = this.expandedFamilyId() === family.spec_id ? null : family.spec_id;
    this.expandedFamilyId.set(next);
    if (next && !this.selectedVersion()) {
      this.selectedVersion.set(family.latest);
    }
  }

  selectVersion(spec: Spec) {
    this.selectedVersion.set(spec);
    this.expandedFamilyId.set(spec.spec_id);
  }

  onSearchInput(value: string) {
    this.searchTerm.set(value);
  }

  downloadSpec(spec: Spec, event?: Event) {
    event?.stopPropagation();
    if (!spec.id) return;
    this.specService.downloadSpecFile(spec.id, spec.file_name);
  }

  openSource(spec: Spec, event?: Event) {
    event?.stopPropagation();
    if (spec.source_url) window.open(spec.source_url, '_blank', 'noopener');
  }

  tagList(tags?: string): string[] {
    if (!tags?.trim()) return [];
    return tags.split(',').map(t => t.trim()).filter(Boolean);
  }

  statusClass(status?: string): string {
    return (status || '').toLowerCase() === 'official' ? 'status-official' : 'status-draft';
  }

  displayProject(): string {
    return this.projectName() || 'Unassigned';
  }

  formatDate(value?: string): string {
    if (!value) return '—';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString(undefined, { dateStyle: 'medium' });
  }

  addSpecToProject(mode: 'new' | 'version' = 'new', family?: SpecFamilyGroup) {
    const project = this.displayProject();
    this.router.navigate(['/specs'], {
      queryParams: {
        add: '1',
        mode,
        project: project === 'Unassigned' ? '' : project,
        ...(family && mode === 'version' ? {
          spec_id: family.spec_id,
          title: family.title,
          category: family.latest.category || '',
        } : {}),
      },
    });
  }
}
