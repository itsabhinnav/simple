import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import {
  AdminService,
  AdminSettingsResponse,
  ImportSchemaResponse,
  ImportTargetSchema,
  LlmConfigResponse,
  LlmTestResponse,
  SchemaTable,
  SchemaTableSummary,
  SchemaColumn,
  SchemaMigrationRow,
  SchemaBackupRow,
  CreateTableColumn,
} from '../services/admin.service';
import { TestCaseService } from '../services/test-case.service';
import { SettingsReloadService } from '../services/settings-reload.service';

type TabId = 'dropdowns' | 'multiValue' | 'features' | 'aliases' | 'targets' | 'llm' | 'schema' | 'sections' | 'readonly';

interface AliasRow { raw: string; target: string | null; }

interface NewColumnDraft {
  name: string;
  type: string;
  nullable: boolean;
  default: string;
  primary_key: boolean;
}

interface ColumnEditDraft {
  new_name: string;
  new_type: string;
  nullable: boolean;
  default: string;
}

@Component({
  selector: 'app-admin-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './admin-settings.component.html',
  styleUrls: [
    './admin-settings.component.scss',
    './admin-settings-schema.component.scss'
  ]
})
export class AdminSettingsComponent implements OnInit {
  private admin = inject(AdminService);
  private testCaseService = inject(TestCaseService);
  protected reloadBus = inject(SettingsReloadService);

  /** SQLite affinity types the admin UI exposes in selects. */
  readonly columnTypes: ReadonlyArray<string> = [
    'TEXT', 'INTEGER', 'REAL', 'NUMERIC', 'BOOLEAN', 'DATETIME', 'DATE', 'BLOB'
  ];

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

  // --- LLM tab state ---
  llm = signal<LlmConfigResponse | null>(null);
  llmDraft = signal<Record<string, Record<string, string>>>({});
  llmDefault = signal<string>('');
  llmTesting = signal<Record<string, boolean>>({});
  llmTestResult = signal<Record<string, LlmTestResponse | null>>({});

  llmProviderNames = computed<string[]>(() => {
    const l = this.llm();
    if (!l) return [];
    const names = new Set<string>([...l.registered, ...Object.keys(l.providers || {}), ...Object.keys(l.schema || {})]);
    return [...names].sort();
  });

  // --- Sections (raw JSON editor) tab state ---
  selectedSection = signal<string>('');
  sectionDraft = signal<string>('');
  sectionDraftError = signal<string | null>(null);

  // --- Schema tab state ---
  schemaTables = signal<SchemaTableSummary[]>([]);
  selectedSchemaTable = signal<string>('');
  currentSchemaTable = signal<SchemaTable | null>(null);
  schemaLoading = signal(false);
  schemaError = signal<string | null>(null);
  newColumnDraft = signal<NewColumnDraft>(this.emptyColumnDraft());
  editingColumn = signal<string | null>(null);
  columnEditDraft = signal<ColumnEditDraft>({ new_name: '', new_type: 'TEXT', nullable: true, default: '' });

  showNewTableModal = signal(false);
  newTableName = signal('');
  newTableColumns = signal<NewColumnDraft[]>([this.emptyColumnDraft({ primary_key: true, type: 'INTEGER', name: 'id', nullable: false })]);

  migrations = signal<SchemaMigrationRow[]>([]);
  backups = signal<SchemaBackupRow[]>([]);
  showMigrations = signal(false);

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
    this.loadLlm();
    this.loadSchema();
  }

  // ----------------------------------------------------------------
  // LLM tab
  // ----------------------------------------------------------------
  loadLlm(): void {
    this.admin.getLlmConfig().subscribe({
      next: cfg => {
        this.llm.set(cfg);
        this.llmDefault.set(cfg.default || '');
        const draft: Record<string, Record<string, string>> = {};
        for (const name of Object.keys(cfg.schema || {})) {
          const fields = cfg.schema[name] || [];
          const current = (cfg.providers || {})[name] || {};
          draft[name] = {};
          for (const f of fields) draft[name][f] = (current[f] ?? '').toString();
        }
        // Also surface any provider that's registered but not in schema map.
        for (const name of cfg.registered) {
          if (!draft[name]) draft[name] = {};
        }
        this.llmDraft.set(draft);
      },
      error: err => this.flash('err', err?.message || 'Failed to load LLM config'),
    });
  }

  llmFieldsFor(name: string): string[] {
    return this.llm()?.schema?.[name] || [];
  }

  llmDraftValue(name: string, field: string): string {
    return this.llmDraft()[name]?.[field] ?? '';
  }

  updateLlmDraft(name: string, field: string, value: string): void {
    const all = { ...this.llmDraft() };
    const per = { ...(all[name] || {}) };
    per[field] = value;
    all[name] = per;
    this.llmDraft.set(all);
  }

  apiKeyState(name: string): { env: string; set: boolean } | null {
    return this.llm()?.api_keys?.[name] ?? null;
  }

  saveLlm(): void {
    this.saving.set(true);
    const providers: Record<string, Record<string, string>> = {};
    for (const [name, fields] of Object.entries(this.llmDraft())) {
      const cleaned: Record<string, string> = {};
      for (const [k, v] of Object.entries(fields)) {
        if (v !== '' && v != null) cleaned[k] = v;
      }
      if (Object.keys(cleaned).length > 0) providers[name] = cleaned;
    }
    this.admin.updateLlmConfig({ default: this.llmDefault(), providers }).subscribe({
      next: () => {
        this.flash('ok', 'LLM configuration saved');
        this.loadLlm();
        // Bubble changes into the global parsing section state so the
        // Advanced tab reflects the new values without a full reload.
        this.reload();
      },
      error: err => this.flash('err', err?.message || 'Save failed'),
      complete: () => this.saving.set(false),
    });
  }

  testLlm(name: string): void {
    const testing = { ...this.llmTesting() };
    testing[name] = true;
    this.llmTesting.set(testing);
    const results = { ...this.llmTestResult() };
    results[name] = null;
    this.llmTestResult.set(results);
    this.admin.testLlmProvider(name).subscribe({
      next: res => {
        const r = { ...this.llmTestResult() };
        r[name] = res;
        this.llmTestResult.set(r);
      },
      error: err => {
        const r = { ...this.llmTestResult() };
        r[name] = { success: false, message: err?.message || 'Test failed' };
        this.llmTestResult.set(r);
      },
      complete: () => {
        const t = { ...this.llmTesting() };
        t[name] = false;
        this.llmTesting.set(t);
      }
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
  // Schema tab — table & column DDL
  // ----------------------------------------------------------------
  private emptyColumnDraft(overrides: Partial<NewColumnDraft> = {}): NewColumnDraft {
    return { name: '', type: 'TEXT', nullable: true, default: '', primary_key: false, ...overrides };
  }

  loadSchema(): void {
    this.schemaLoading.set(true);
    this.schemaError.set(null);
    this.admin.listSchemaTables().subscribe({
      next: tables => {
        this.schemaTables.set(tables);
        if (!this.selectedSchemaTable() && tables.length > 0) {
          const firstEditable = tables.find(t => !t.protected) || tables[0];
          this.selectedSchemaTable.set(firstEditable.name);
          this.loadSchemaTable(firstEditable.name);
        } else if (this.selectedSchemaTable()) {
          this.loadSchemaTable(this.selectedSchemaTable());
        }
      },
      error: err => this.schemaError.set(err?.message || 'Failed to load tables'),
      complete: () => this.schemaLoading.set(false),
    });
    this.loadMigrations();
  }

  selectSchemaTable(name: string): void {
    this.selectedSchemaTable.set(name);
    this.editingColumn.set(null);
    this.loadSchemaTable(name);
  }

  loadSchemaTable(name: string): void {
    if (!name) return;
    this.admin.getSchemaTable(name).subscribe({
      next: t => this.currentSchemaTable.set(t),
      error: err => this.flash('err', err?.message || 'Failed to load table'),
    });
  }

  loadMigrations(): void {
    this.admin.listSchemaMigrations().subscribe({
      next: r => {
        this.migrations.set(r.migrations || []);
        this.backups.set(r.backups || []);
      },
      error: () => { /* non-fatal */ },
    });
  }

  // --- Add column on current table ---
  updateNewColumn<K extends keyof NewColumnDraft>(key: K, value: NewColumnDraft[K]): void {
    this.newColumnDraft.set({ ...this.newColumnDraft(), [key]: value });
  }

  resetNewColumn(): void {
    this.newColumnDraft.set(this.emptyColumnDraft());
  }

  addColumnToCurrentTable(): void {
    const table = this.selectedSchemaTable();
    const draft = this.newColumnDraft();
    if (!table || !draft.name.trim()) return;
    const payload: CreateTableColumn = {
      name: draft.name.trim(),
      type: draft.type,
      nullable: draft.nullable,
      default: draft.default !== '' ? draft.default : undefined,
      primary_key: false,
    };
    this.saving.set(true);
    this.admin.addSchemaColumn(table, payload).subscribe({
      next: t => {
        this.currentSchemaTable.set(t);
        this.resetNewColumn();
        this.flash('ok', `Column '${payload.name}' added to ${table}`);
        this.afterSchemaChange(`Added column ${payload.name} to ${table}`);
      },
      error: err => this.flash('err', err?.message || 'Failed to add column'),
      complete: () => this.saving.set(false),
    });
  }

  // --- Edit column (rename + retype + nullability + default) ---
  startEditColumn(col: SchemaColumn): void {
    this.editingColumn.set(col.name);
    this.columnEditDraft.set({
      new_name: col.name,
      new_type: (col.type || 'TEXT').toString().toUpperCase(),
      nullable: col.nullable,
      default: col.default == null ? '' : String(col.default),
    });
  }

  cancelEditColumn(): void {
    this.editingColumn.set(null);
  }

  updateColumnEdit<K extends keyof ColumnEditDraft>(key: K, value: ColumnEditDraft[K]): void {
    this.columnEditDraft.set({ ...this.columnEditDraft(), [key]: value });
  }

  saveColumnEdit(): void {
    const table = this.selectedSchemaTable();
    const original = this.editingColumn();
    if (!table || !original) return;
    const draft = this.columnEditDraft();
    const payload = {
      new_name: draft.new_name && draft.new_name !== original ? draft.new_name : undefined,
      new_type: draft.new_type || undefined,
      nullable: draft.nullable,
      default: draft.default !== '' ? draft.default : null,
    };
    this.saving.set(true);
    this.admin.updateSchemaColumn(table, original, payload).subscribe({
      next: t => {
        this.currentSchemaTable.set(t);
        this.editingColumn.set(null);
        this.flash('ok', `Column '${original}' updated`);
        this.afterSchemaChange(`Updated column ${original} on ${table}`);
      },
      error: err => this.flash('err', err?.message || 'Failed to update column'),
      complete: () => this.saving.set(false),
    });
  }

  deleteColumn(col: SchemaColumn): void {
    const table = this.selectedSchemaTable();
    if (!table) return;
    if (col.primary_key) {
      this.flash('err', 'Cannot drop a primary key column');
      return;
    }
    const ok = window.confirm(`Drop column "${col.name}" from "${table}"? This is irreversible.`);
    if (!ok) return;
    this.saving.set(true);
    this.admin.dropSchemaColumn(table, col.name).subscribe({
      next: t => {
        this.currentSchemaTable.set(t);
        this.flash('ok', `Column '${col.name}' dropped`);
        this.afterSchemaChange(`Dropped column ${col.name} from ${table}`);
      },
      error: err => this.flash('err', err?.message || 'Failed to drop column'),
      complete: () => this.saving.set(false),
    });
  }

  // --- Create new table ---
  openNewTableModal(): void {
    this.newTableName.set('');
    this.newTableColumns.set([
      this.emptyColumnDraft({ name: 'id', type: 'INTEGER', primary_key: true, nullable: false }),
    ]);
    this.showNewTableModal.set(true);
  }

  closeNewTableModal(): void {
    this.showNewTableModal.set(false);
  }

  addNewTableColumn(): void {
    this.newTableColumns.set([...this.newTableColumns(), this.emptyColumnDraft()]);
  }

  removeNewTableColumn(index: number): void {
    const next = this.newTableColumns().filter((_, i) => i !== index);
    this.newTableColumns.set(next.length > 0 ? next : [this.emptyColumnDraft()]);
  }

  updateNewTableColumn<K extends keyof NewColumnDraft>(index: number, key: K, value: NewColumnDraft[K]): void {
    const list = [...this.newTableColumns()];
    list[index] = { ...list[index], [key]: value };
    this.newTableColumns.set(list);
  }

  submitNewTable(): void {
    const name = this.newTableName().trim();
    if (!name) {
      this.flash('err', 'Table name is required');
      return;
    }
    const payload: CreateTableColumn[] = this.newTableColumns()
      .filter(c => c.name.trim())
      .map(c => ({
        name: c.name.trim(),
        type: c.type,
        nullable: c.nullable,
        default: c.default !== '' ? c.default : undefined,
        primary_key: c.primary_key,
      }));
    if (payload.length === 0) {
      this.flash('err', 'At least one column is required');
      return;
    }
    this.saving.set(true);
    this.admin.createSchemaTable(name, payload).subscribe({
      next: t => {
        this.closeNewTableModal();
        this.selectedSchemaTable.set(t.name);
        this.currentSchemaTable.set(t);
        this.loadSchema();
        this.flash('ok', `Table '${name}' created`);
        this.afterSchemaChange(`Created table ${name}`);
      },
      error: err => this.flash('err', err?.message || 'Failed to create table'),
      complete: () => this.saving.set(false),
    });
  }

  // --- Drop table ---
  dropCurrentTable(): void {
    const name = this.selectedSchemaTable();
    if (!name) return;
    const typed = window.prompt(
      `Type the table name "${name}" to confirm permanent deletion:`,
      '',
    );
    if (typed !== name) {
      if (typed !== null) this.flash('err', 'Confirmation did not match — not dropped');
      return;
    }
    this.saving.set(true);
    this.admin.dropSchemaTable(name).subscribe({
      next: () => {
        this.selectedSchemaTable.set('');
        this.currentSchemaTable.set(null);
        this.loadSchema();
        this.flash('ok', `Table '${name}' dropped`);
        this.afterSchemaChange(`Dropped table ${name}`);
      },
      error: err => this.flash('err', err?.message || 'Failed to drop table'),
      complete: () => this.saving.set(false),
    });
  }

  createBackup(): void {
    this.saving.set(true);
    this.admin.createSchemaBackup().subscribe({
      next: r => {
        this.flash('ok', `Backup created (${this.formatBytes(r.size_bytes)})`);
        this.loadMigrations();
      },
      error: err => this.flash('err', err?.message || 'Backup failed'),
      complete: () => this.saving.set(false),
    });
  }

  toggleMigrations(): void {
    this.showMigrations.set(!this.showMigrations());
    if (this.showMigrations()) this.loadMigrations();
  }

  formatBytes(bytes: number): string {
    if (!bytes && bytes !== 0) return '—';
    const units = ['B', 'KB', 'MB', 'GB'];
    let v = bytes;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
  }

  /**
   * Trigger a delayed full reload of the SPA after a schema change. The
   * delay lets the success toast flash briefly. We also broadcast the
   * intent so other open tabs reload together.
   */
  private afterSchemaChange(reason: string): void {
    this.reloadBus.scheduleReload(reason, 1500);
  }

  /** Explicit "Restart app" button used by the header. */
  restartApp(): void {
    this.reloadBus.reloadNow('Manual restart');
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
