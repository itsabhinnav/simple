import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import {
  AdminService,
  AdminSettingsResponse,
  ImportSchemaResponse,
  ImportTargetSchema,
} from '../services/admin.service';
import { TestCaseService } from '../services/test-case.service';

type TabId = 'dropdowns' | 'multiValue' | 'features' | 'aliases' | 'targets' | 'sections' | 'readonly';

interface AliasRow { raw: string; target: string | null; }

@Component({
  selector: 'app-admin-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './admin-settings.component.html',
  styleUrl: './admin-settings.component.scss'
})
export class AdminSettingsComponent implements OnInit {
  private admin = inject(AdminService);
  private testCaseService = inject(TestCaseService);

  loading = signal(true);
  saving = signal(false);
  error = signal<string | null>(null);
  toast = signal<{ kind: 'ok' | 'err'; msg: string } | null>(null);

  settings = signal<AdminSettingsResponse | null>(null);
  schema = signal<ImportSchemaResponse | null>(null);

  activeTab = signal<TabId>('dropdowns');

  // --- Dropdowns tab state ---
  dropdownFields = computed<string[]>(() => {
    const dd = this.settings()?.sections?.['test_case_dropdowns'] || {};
    return Object.keys(dd).filter(k => k !== 'multi_value_fields').sort();
  });
  selectedDropdownField = signal<string>('');
  newOption = signal<string>('');

  // --- Multi-value fields tab state ---
  // candidate fields = union of currently-multi + every dropdown field that
  // exists in the dropdowns block. Admins can add free-form ones too.
  multiValueFields = computed<string[]>(() => {
    const dd = this.settings()?.sections?.['test_case_dropdowns'] || {};
    return (dd['multi_value_fields'] || []) as string[];
  });
  newMultiValueField = signal<string>('');

  // --- Features tab state ---
  featureKeys = computed<string[]>(() =>
    Object.keys(this.settings()?.sections?.['features'] || {}).sort()
  );

  // --- Aliases tab state ---
  aliasRows = signal<AliasRow[]>([]);
  newAliasRaw = signal<string>('');
  newAliasTarget = signal<string>('');

  // --- Target fields tab state ---
  targetNames = computed<string[]>(() => {
    const sch = this.schema();
    return sch ? Object.keys(sch.targets).sort() : [];
  });
  selectedTarget = signal<string>('');
  targetFieldsDraft = signal<string[]>([]);
  targetRequiredDraft = signal<string[]>([]);
  newTargetField = signal<string>('');

  // --- Sections (raw JSON editor) tab state ---
  selectedSection = signal<string>('');
  sectionDraft = signal<string>('');
  sectionDraftError = signal<string | null>(null);

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.admin.getSettings().subscribe({
      next: data => {
        this.settings.set(data);
        // Initialize per-tab selections to first available item.
        if (!this.selectedDropdownField()) {
          const first = this.dropdownFields()[0] || '';
          this.selectedDropdownField.set(first);
        }
        if (!this.selectedSection()) {
          this.selectedSection.set(data.editable_sections[0] || '');
          this.syncSectionDraft();
        }
        // Hydrate alias rows from current bulk_import overlay.
        const overlay = (data.sections?.['bulk_import']?.header_aliases || {}) as Record<string, string | null>;
        this.aliasRows.set(
          Object.entries(overlay).map(([raw, target]) => ({ raw, target: target ?? null }))
        );
      },
      error: err => this.error.set(err?.message || 'Failed to load settings'),
      complete: () => this.loading.set(false),
    });
    this.admin.getImportSchema().subscribe({
      next: sch => {
        this.schema.set(sch);
        if (!this.selectedTarget()) {
          const first = Object.keys(sch.targets).sort()[0] || '';
          this.selectedTarget.set(first);
          this.syncTargetDraft();
        }
      },
      error: () => { /* leave schema null; tab will show message */ }
    });
  }

  setTab(tab: TabId): void { this.activeTab.set(tab); }

  // ----------------------------------------------------------------
  // Dropdowns tab
  // ----------------------------------------------------------------
  selectDropdownField(field: string): void {
    this.selectedDropdownField.set(field);
    this.newOption.set('');
  }

  optionsFor(field: string): string[] {
    const dd = this.settings()?.sections?.['test_case_dropdowns'] || {};
    const val = dd[field];
    return Array.isArray(val) ? val.map(v => String(v)) : [];
  }

  addOption(): void {
    const field = this.selectedDropdownField();
    const value = this.newOption().trim();
    if (!field || !value) return;
    const dd = { ...(this.settings()?.sections?.['test_case_dropdowns'] || {}) };
    const current = Array.isArray(dd[field]) ? [...dd[field]] : [];
    if (current.includes(value)) {
      this.flash('err', `'${value}' already exists in ${field}`);
      return;
    }
    current.push(value);
    dd[field] = current;
    this.persistDropdowns(dd);
    this.newOption.set('');
  }

  removeOption(field: string, value: string): void {
    const dd = { ...(this.settings()?.sections?.['test_case_dropdowns'] || {}) };
    const current = (dd[field] || []).filter((v: string) => v !== value);
    dd[field] = current;
    this.persistDropdowns(dd);
  }

  private persistDropdowns(dd: Record<string, any>): void {
    this.saveSection('test_case_dropdowns', dd, 'Dropdown options updated');
  }

  // ----------------------------------------------------------------
  // Multi-value fields tab
  // ----------------------------------------------------------------
  toggleMultiValue(field: string): void {
    const dd = { ...(this.settings()?.sections?.['test_case_dropdowns'] || {}) };
    const list: string[] = Array.isArray(dd['multi_value_fields']) ? [...dd['multi_value_fields']] : [];
    const idx = list.indexOf(field);
    if (idx >= 0) list.splice(idx, 1); else list.push(field);
    dd['multi_value_fields'] = list;
    this.persistDropdowns(dd);
  }

  addMultiValueField(): void {
    const v = this.newMultiValueField().trim();
    if (!v) return;
    const dd = { ...(this.settings()?.sections?.['test_case_dropdowns'] || {}) };
    const list: string[] = Array.isArray(dd['multi_value_fields']) ? [...dd['multi_value_fields']] : [];
    if (list.includes(v)) {
      this.flash('err', `'${v}' is already multi-value`);
      return;
    }
    list.push(v);
    dd['multi_value_fields'] = list;
    this.persistDropdowns(dd);
    this.newMultiValueField.set('');
  }

  // Any field we want to surface for the multi-value toggle UI. Union of
  // configured dropdown fields and any names already marked multi-value.
  allTrackedFields = computed<string[]>(() => {
    const set = new Set<string>([...this.dropdownFields(), ...this.multiValueFields()]);
    return [...set].sort();
  });

  isMultiValue(field: string): boolean { return this.multiValueFields().includes(field); }

  // ----------------------------------------------------------------
  // Features tab
  // ----------------------------------------------------------------
  toggleFeature(key: string): void {
    const features = { ...(this.settings()?.sections?.['features'] || {}) };
    features[key] = !features[key];
    this.saveSection('features', features, `Feature '${key}' ${features[key] ? 'enabled' : 'disabled'}`);
  }

  featureValue(key: string): boolean {
    return !!(this.settings()?.sections?.['features'] || {})[key];
  }

  // ----------------------------------------------------------------
  // Aliases tab
  // ----------------------------------------------------------------
  addAlias(): void {
    const raw = this.newAliasRaw().trim().toLowerCase();
    const target = this.newAliasTarget().trim();
    if (!raw) return;
    const rows = [...this.aliasRows()];
    const existing = rows.findIndex(r => r.raw === raw);
    const entry: AliasRow = { raw, target: target || null };
    if (existing >= 0) rows[existing] = entry; else rows.push(entry);
    this.aliasRows.set(rows);
    this.newAliasRaw.set('');
    this.newAliasTarget.set('');
    this.persistAliases();
  }

  removeAlias(raw: string): void {
    this.aliasRows.set(this.aliasRows().filter(r => r.raw !== raw));
    this.persistAliases();
  }

  updateAliasTarget(raw: string, target: string): void {
    this.aliasRows.set(this.aliasRows().map(r => r.raw === raw ? { ...r, target: target || null } : r));
    this.persistAliases();
  }

  private persistAliases(): void {
    const overlay: Record<string, string | null> = {};
    for (const r of this.aliasRows()) overlay[r.raw] = r.target;
    const bulk = { ...(this.settings()?.sections?.['bulk_import'] || {}) };
    bulk['header_aliases'] = overlay;
    this.saveSection('bulk_import', bulk, 'Column aliases updated');
  }

  // ----------------------------------------------------------------
  // Targets tab
  // ----------------------------------------------------------------
  selectTarget(name: string): void {
    this.selectedTarget.set(name);
    this.syncTargetDraft();
  }

  private syncTargetDraft(): void {
    const t: ImportTargetSchema | undefined = this.schema()?.targets[this.selectedTarget()];
    this.targetFieldsDraft.set(t ? [...t.fields] : []);
    this.targetRequiredDraft.set(t ? [...t.required] : []);
    this.newTargetField.set('');
  }

  currentTarget(): ImportTargetSchema | null {
    const sch = this.schema();
    const name = this.selectedTarget();
    return sch && name ? sch.targets[name] || null : null;
  }

  toggleRequired(field: string): void {
    const list = [...this.targetRequiredDraft()];
    const idx = list.indexOf(field);
    if (idx >= 0) list.splice(idx, 1); else list.push(field);
    this.targetRequiredDraft.set(list);
  }

  removeTargetField(field: string): void {
    this.targetFieldsDraft.set(this.targetFieldsDraft().filter(f => f !== field));
    this.targetRequiredDraft.set(this.targetRequiredDraft().filter(f => f !== field));
  }

  addTargetField(): void {
    const v = this.newTargetField().trim();
    if (!v) return;
    const list = this.targetFieldsDraft();
    if (list.includes(v)) {
      this.flash('err', `'${v}' already exists`);
      return;
    }
    this.targetFieldsDraft.set([...list, v]);
    this.newTargetField.set('');
  }

  persistTargetFields(): void {
    const target = this.selectedTarget();
    if (!target) return;
    const bulk = { ...(this.settings()?.sections?.['bulk_import'] || {}) };
    const tf = { ...(bulk['target_fields'] || {}) };
    tf[target] = {
      fields: this.targetFieldsDraft(),
      required: this.targetRequiredDraft(),
    };
    bulk['target_fields'] = tf;
    this.saveSection('bulk_import', bulk, `Schema for '${target}' saved`, () => {
      // Re-fetch import schema so cached effective fields reflect server-side merge.
      this.admin.getImportSchema().subscribe({ next: sch => this.schema.set(sch) });
    });
  }

  resetTargetFields(): void {
    const target = this.selectedTarget();
    if (!target) return;
    const t = this.schema()?.targets[target];
    if (!t) return;
    this.targetFieldsDraft.set([...t.default_fields]);
    this.targetRequiredDraft.set([...t.default_required]);
    const bulk = { ...(this.settings()?.sections?.['bulk_import'] || {}) };
    const tf = { ...(bulk['target_fields'] || {}) };
    delete tf[target];
    bulk['target_fields'] = tf;
    this.saveSection('bulk_import', bulk, `Schema for '${target}' reset to defaults`, () => {
      this.admin.getImportSchema().subscribe({ next: sch => this.schema.set(sch) });
    });
  }

  // ----------------------------------------------------------------
  // Raw-section JSON editor
  // ----------------------------------------------------------------
  selectSection(name: string): void {
    this.selectedSection.set(name);
    this.syncSectionDraft();
  }

  private syncSectionDraft(): void {
    const s = this.settings();
    const name = this.selectedSection();
    if (!s || !name) { this.sectionDraft.set(''); return; }
    this.sectionDraft.set(JSON.stringify(s.sections[name] ?? {}, null, 2));
    this.sectionDraftError.set(null);
  }

  saveSectionDraft(): void {
    const name = this.selectedSection();
    if (!name) return;
    let parsed: any;
    try {
      parsed = JSON.parse(this.sectionDraft());
    } catch (e: any) {
      this.sectionDraftError.set(`Invalid JSON: ${e?.message || 'parse error'}`);
      return;
    }
    this.sectionDraftError.set(null);
    this.saveSection(name, parsed, `Section '${name}' saved`);
  }

  // ----------------------------------------------------------------
  // Read-only sections (displayed as JSON)
  // ----------------------------------------------------------------
  readOnlyJson(name: string): string {
    return JSON.stringify(this.settings()?.sections?.[name] ?? {}, null, 2);
  }

  // ----------------------------------------------------------------
  // Generic save helper
  // ----------------------------------------------------------------
  private saveSection(section: string, value: any, okMsg: string, after?: () => void): void {
    this.saving.set(true);
    this.admin.updateSection(section, value).subscribe({
      next: (resp) => {
        const s = this.settings();
        if (s) {
          this.settings.set({ ...s, sections: { ...s.sections, [section]: resp.value } });
        }
        // Invalidate downstream caches so create/detail screens see new
        // pickers immediately without a full page reload.
        if (section === 'test_case_dropdowns') {
          this.testCaseService.getDropdowns(true).subscribe({ error: () => { /* ignore */ } });
        }
        this.flash('ok', okMsg);
        if (after) after();
      },
      error: err => this.flash('err', err?.message || 'Save failed'),
      complete: () => this.saving.set(false),
    });
  }

  private flash(kind: 'ok' | 'err', msg: string): void {
    this.toast.set({ kind, msg });
    setTimeout(() => {
      if (this.toast()?.msg === msg) this.toast.set(null);
    }, 3500);
  }
}
