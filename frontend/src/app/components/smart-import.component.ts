import {
  Component,
  OnInit,
  PLATFORM_ID,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { CommonModule, Location, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import {
  BulkImportDuplicateStrategy,
  BulkImportFileResult,
  BulkImportPreview,
  BulkImportResult,
  BulkImportService,
  BulkImportSheetPreview,
} from '../services/bulk-import.service';
import {
  ImportTarget,
  ParsingService,
  SmartPreviewAi,
  SmartPreviewResponse,
} from '../services/parsing.service';

/**
 * Smart Import wizard — used for ALL four bulk-import targets
 * (specifications, requirements, design_tickets, test_cases).
 *
 * Two parallel pipelines are wired up:
 *
 * 1. Deterministic header detection + DB write (`BulkImportService`) —
 *    authoritative for ID uniqueness, required-field enforcement and
 *    column-mapping. Unchanged from the previous test-case flow.
 *
 * 2. AI-driven enrichment (`ParsingService.smartPreview`) — surfaces
 *    artifact classification, semantic overlays, recommended VLM
 *    provider, image-anchor counts. Best-effort; failures degrade
 *    gracefully and never block the deterministic path.
 *
 * The component is target-agnostic. The active target is read from
 * `ActivatedRoute.data.target` so a single component can serve
 * `/specs/import`, `/requirements/import`, `/design-tickets/import`
 * and `/test-cases/import`.
 */
interface FilePreviewEntry {
  file: File;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error: string | null;
  preview: BulkImportPreview | null;
  ai: SmartPreviewAi | null;
}

interface MappingPreset {
  id: string;
  name: string;
  createdAt: string;
  mapping: { [rawHeader: string]: string };
}

interface ImportHistoryEntry {
  at: string;
  files: string[];
  totals: { created: number; updated: number; skipped: number; failed: number };
  strategy: BulkImportDuplicateStrategy;
  target: ImportTarget;
}

type WizardStep = 'upload' | 'map' | 'review' | 'result';

const PRESETS_KEY_BASE = 'sakura.smart-import.presets.v1';
const HISTORY_KEY = 'sakura.smart-import.history.v1';
const HISTORY_LIMIT = 8;

@Component({
  selector: 'app-smart-import',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './smart-import.component.html',
  styleUrl: './smart-import.component.scss',
})
export class SmartImportComponent implements OnInit {
  private bulkImport = inject(BulkImportService);
  private parsing = inject(ParsingService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private location = inject(Location);
  private platformId = inject(PLATFORM_ID);

  // -------------------- Target (driven by route data) --------------------
  target = signal<ImportTarget>('test_cases');
  targetLabel = computed(() => this.bulkImport.label(this.target()));
  viewListPath = computed(() => this.bulkImport.routePath(this.target()));

  // -------------------- Wizard state --------------------
  readonly steps: { id: WizardStep; label: string }[] = [
    { id: 'upload', label: 'Upload' },
    { id: 'map', label: 'Map columns' },
    { id: 'review', label: 'Review' },
    { id: 'result', label: 'Result' },
  ];
  step = signal<WizardStep>('upload');

  // -------------------- Files & previews --------------------
  files = signal<FilePreviewEntry[]>([]);
  isDragging = signal(false);
  activeFileIndex = signal(0);
  activeSheetIndex = signal(0);

  // -------------------- Mapping --------------------
  importFields = signal<string[]>([]);
  requiredFields = signal<string[]>([]);
  importMapping = signal<{ [rawHeader: string]: string }>({});
  mappingFilter = '';
  showAdvancedMapping = signal(false);

  // -------------------- AI enrichment --------------------
  enableAi = signal<boolean>(false);
  enableVisual = signal<boolean>(false);
  enableVlm = signal<boolean>(false);
  providers = signal<string[]>([]);
  defaultProvider = signal<string | null>(null);
  selectedProvider = signal<string | null>(null);
  aiBusy = signal(false);

  // -------------------- Presets / history --------------------
  presets = signal<MappingPreset[]>([]);
  activePresetId = signal<string>('');
  showSavePresetForm = signal(false);
  newPresetName = '';
  history = signal<ImportHistoryEntry[]>([]);

  // -------------------- Import execution --------------------
  strategy = signal<BulkImportDuplicateStrategy>('skip');
  isImporting = signal(false);
  importResult = signal<BulkImportResult | null>(null);
  importError = signal<string | null>(null);

  // -------------------- Derived --------------------
  readyCount = computed(() => this.files().filter((f) => f.status === 'ready').length);
  isPreviewingAny = computed(() => this.files().some((f) => f.status === 'loading'));
  activeEntry = computed<FilePreviewEntry | undefined>(() => this.files()[this.activeFileIndex()]);
  hasAnyReadyPreview = computed(() => this.files().some((f) => f.status === 'ready'));

  totalSheets = computed(() =>
    this.files().reduce((sum, e) => sum + (e.preview?.sheets.length || 0), 0),
  );
  totalRows = computed(() =>
    this.files().reduce(
      (sum, e) => sum + (e.preview?.sheets.reduce((s, sh) => s + (sh.row_count_estimate || 0), 0) || 0),
      0,
    ),
  );
  totalMappedColumns = computed(() => Object.keys(this.importMapping()).length);

  artifactKindFromAi = computed<string | null>(() => {
    const ai = this.files().find((f) => f.ai && !f.ai.skipped)?.ai;
    return ai?.artifact_kind || null;
  });

  mappingWarnings = computed<string[]>(() => {
    const warnings: string[] = [];
    const mapped = new Set(Object.values(this.importMapping()));
    this.requiredFields().forEach((req) => {
      if (!mapped.has(req)) {
        warnings.push(
          `Required field "${req}" is not mapped to any column. Rows without it will be auto-generated by the server.`,
        );
      }
    });
    const counts: Record<string, number> = {};
    Object.values(this.importMapping()).forEach((v) => {
      counts[v] = (counts[v] || 0) + 1;
    });
    Object.entries(counts).forEach(([field, count]) => {
      if (count > 1) {
        warnings.push(`Field "${field}" is mapped from ${count} different columns — the last one wins.`);
      }
    });
    const aiKind = this.artifactKindFromAi();
    if (aiKind && aiKind !== 'unknown' && !this.target().includes(aiKind.replace('test_cases', 'test_cases'))) {
      warnings.push(
        `AI classified this file as "${aiKind}" but you're importing into ${this.targetLabel().plural}. Double-check the target.`,
      );
    }
    return warnings;
  });

  constructor() {
    // Persist presets / history scoped per target.
    effect(() => {
      const list = this.presets();
      const t = this.target();
      if (isPlatformBrowser(this.platformId)) {
        try {
          localStorage.setItem(`${PRESETS_KEY_BASE}.${t}`, JSON.stringify(list));
        } catch {
          /* quota — ignore */
        }
      }
    });
    effect(() => {
      const list = this.history();
      if (isPlatformBrowser(this.platformId)) {
        try {
          localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
        } catch {
          /* quota — ignore */
        }
      }
    });
    effect(() => {
      const t = this.target();
      // Reload presets when the active target changes.
      if (isPlatformBrowser(this.platformId)) {
        try {
          const raw = localStorage.getItem(`${PRESETS_KEY_BASE}.${t}`);
          this.presets.set(raw ? JSON.parse(raw) : []);
        } catch {
          this.presets.set([]);
        }
      }
    });
  }

  ngOnInit(): void {
    const dataTarget = (this.route.snapshot.data?.['target'] as ImportTarget) || 'test_cases';
    this.target.set(dataTarget);

    this.bulkImport.getImportFields(dataTarget).subscribe({
      next: (res) => {
        this.importFields.set(res.fields || []);
        if (res.required?.length) this.requiredFields.set(res.required);
      },
      error: () => {
        this.importFields.set(this.fallbackFields(dataTarget));
        this.requiredFields.set(this.fallbackRequired(dataTarget));
      },
    });

    this.parsing.listProviders().subscribe((res) => {
      this.providers.set(res.providers || []);
      this.defaultProvider.set(res.default || null);
      if (!this.selectedProvider()) this.selectedProvider.set(res.default || null);
    });

    if (isPlatformBrowser(this.platformId)) {
      try {
        const raw = localStorage.getItem(HISTORY_KEY);
        if (raw) this.history.set(JSON.parse(raw));
      } catch {
        /* corrupt JSON — reset silently */
      }
    }
  }

  // -------------------- Navigation helpers --------------------
  goBack() {
    this.location.back();
  }

  stepIndex(s: WizardStep): number {
    return this.steps.findIndex((x) => x.id === s);
  }

  jumpToStep(target: WizardStep) {
    if (target === 'result' && !this.importResult()) return;
    if (target === 'map' && this.files().length === 0) return;
    if (target === 'review' && !this.hasAnyReadyPreview() && this.files().length === 0) return;
    this.step.set(target);
  }

  // -------------------- Drag & drop / file selection --------------------
  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(true);
  }
  onDragLeave(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(false);
  }
  onDrop(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(false);
    const dropped = Array.from(e.dataTransfer?.files || []);
    this.addFiles(dropped);
  }
  onFileInputChange(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files) return;
    this.addFiles(Array.from(input.files));
    input.value = '';
  }

  private addFiles(picked: File[]) {
    if (picked.length === 0) return;
    // Allow xlsx/xlsm/csv for the deterministic path AND docx for the AI
    // path (deterministic preview will return zero sheets — the wizard
    // surfaces the AI-only result in that case).
    const allowed = /\.(xlsx|xlsm|csv|docx)$/i;
    const filtered = picked.filter((f) => allowed.test(f.name));
    if (filtered.length === 0) {
      this.importError.set('No supported files. Use .xlsx, .xlsm, .csv, or .docx.');
      return;
    }
    this.importError.set(null);
    const existingNames = new Set(this.files().map((e) => e.file.name + ':' + e.file.size));
    const additions: FilePreviewEntry[] = filtered
      .filter((f) => !existingNames.has(f.name + ':' + f.size))
      .map((f) => ({ file: f, status: 'idle' as const, error: null, preview: null, ai: null }));
    if (additions.length === 0) return;
    this.files.set([...this.files(), ...additions]);
  }

  removeFile(index: number) {
    const next = this.files().slice();
    next.splice(index, 1);
    this.files.set(next);
    if (this.activeFileIndex() >= next.length) this.activeFileIndex.set(Math.max(0, next.length - 1));
  }

  clearFiles() {
    this.files.set([]);
    this.activeFileIndex.set(0);
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  sheetCountFor(entry: FilePreviewEntry): number {
    return entry.preview?.sheets.length || 0;
  }

  // -------------------- Preview --------------------
  goToMap() {
    const pending = this.files()
      .map((e, i) => ({ e, i }))
      .filter((x) => x.e.status === 'idle' || x.e.status === 'error');

    if (pending.length === 0) {
      this.afterPreviewsSettled();
      return;
    }
    this.mutateFiles((arr) =>
      pending.forEach((p) => {
        arr[p.i] = { ...arr[p.i], status: 'loading', error: null };
      }),
    );

    const useAi = this.enableAi();
    const calls = pending.map((p) =>
      useAi
        ? this.parsing
            .smartPreview(p.e.file, {
              target: this.target(),
              provider: this.selectedProvider() || undefined,
              sampleRows: 5,
              enableAi: true,
              enableVisual: this.enableVisual(),
              enableVlm: this.enableVlm(),
            })
            .pipe(
              map((res: SmartPreviewResponse) => ({
                i: p.i,
                ok: true as const,
                preview: res.deterministic as BulkImportPreview,
                ai: res.ai,
              })),
              catchError((err) => of({ i: p.i, ok: false as const, error: this.formatError(err) })),
            )
        : this.bulkImport.preview(this.target(), p.e.file).pipe(
            map((preview) => ({ i: p.i, ok: true as const, preview, ai: null })),
            catchError((err) => of({ i: p.i, ok: false as const, error: this.formatError(err) })),
          ),
    );

    this.aiBusy.set(useAi);
    forkJoin(calls).subscribe((results) => {
      this.mutateFiles((arr) => {
        results.forEach((r) => {
          if (r.ok) {
            arr[r.i] = {
              ...arr[r.i],
              status: 'ready',
              preview: r.preview,
              ai: r.ai ?? null,
              error: null,
            };
          } else {
            arr[r.i] = { ...arr[r.i], status: 'error', preview: null, ai: null, error: r.error };
          }
        });
      });
      this.aiBusy.set(false);
      this.afterPreviewsSettled();
    });
  }

  previewFile(index: number) {
    const entry = this.files()[index];
    if (!entry) return;
    this.mutateFiles((arr) => {
      arr[index] = { ...arr[index], status: 'loading', error: null };
    });
    this.bulkImport.preview(this.target(), entry.file).subscribe({
      next: (preview) =>
        this.mutateFiles((arr) => {
          arr[index] = { ...arr[index], status: 'ready', preview, error: null };
          this.seedMappingFromAllPreviews();
        }),
      error: (err) =>
        this.mutateFiles((arr) => {
          arr[index] = {
            ...arr[index],
            status: 'error',
            preview: null,
            ai: null,
            error: this.formatError(err),
          };
        }),
    });
  }

  private afterPreviewsSettled() {
    this.seedMappingFromAllPreviews();
    this.activeFileIndex.set(Math.max(0, this.files().findIndex((f) => f.status === 'ready')));
    this.activeSheetIndex.set(0);
    this.step.set('map');
  }

  private seedMappingFromAllPreviews() {
    const seed: { [raw: string]: string } = { ...this.importMapping() };
    this.files().forEach((entry) => {
      entry.preview?.sheets.forEach((sheet) => {
        Object.entries(sheet.suggested_mapping || {}).forEach(([raw, field]) => {
          if (field && !seed[raw]) seed[raw] = field;
        });
      });
    });
    this.importMapping.set(seed);
  }

  setActiveFile(index: number) {
    this.activeFileIndex.set(index);
    this.activeSheetIndex.set(0);
    const entry = this.files()[index];
    if (entry && entry.status === 'idle') this.previewFile(index);
  }

  // -------------------- Mapping helpers --------------------
  getMappingValue(rawHeader: string): string {
    return this.importMapping()[rawHeader] || '';
  }
  setMappingValue(rawHeader: string, value: string) {
    const next = { ...this.importMapping() };
    if (value) next[rawHeader] = value;
    else delete next[rawHeader];
    this.importMapping.set(next);
  }

  isRequired(field: string): boolean {
    return this.requiredFields().includes(field);
  }
  isRequiredHeader(rawHeader: string): boolean {
    return this.isRequired(this.getMappingValue(rawHeader));
  }

  filteredHeaders(sheet: BulkImportSheetPreview): string[] {
    const q = this.mappingFilter.trim().toLowerCase();
    if (!q) return sheet.raw_headers;
    return sheet.raw_headers.filter(
      (h) => h.toLowerCase().includes(q) || (this.getMappingValue(h) || '').toLowerCase().includes(q),
    );
  }

  headerIndex(sheet: BulkImportSheetPreview, header: string): number {
    return sheet.raw_headers.indexOf(header);
  }

  sampleValueFor(sheet: BulkImportSheetPreview, columnIndex: number): string | null {
    if (columnIndex < 0) return null;
    for (const row of sheet.sample_rows) {
      const v = row[columnIndex];
      if (v !== null && v !== undefined && String(v).trim() !== '') return String(v);
    }
    return null;
  }

  mappedColumnCount(sheet: BulkImportSheetPreview): number {
    return sheet.raw_headers.filter((h) => this.getMappingValue(h)).length;
  }

  missingRequired(sheet: BulkImportSheetPreview): string[] {
    const mapped = new Set(sheet.raw_headers.map((h) => this.getMappingValue(h)).filter(Boolean));
    return this.requiredFields().filter((req) => !mapped.has(req));
  }

  mappedColumns(sheet: BulkImportSheetPreview): { index: number; field: string }[] {
    return sheet.raw_headers
      .map((h, i) => ({ index: i, field: this.getMappingValue(h) }))
      .filter((c) => !!c.field);
  }

  previewSampleCount(sheet: BulkImportSheetPreview): number {
    return sheet.sample_rows?.length || 0;
  }

  // -------------------- Bulk mapping ops --------------------
  setAllToIgnore(sheet: BulkImportSheetPreview) {
    const next = { ...this.importMapping() };
    sheet.raw_headers.forEach((h) => {
      delete next[h];
    });
    this.importMapping.set(next);
  }

  applySuggestionForSheet(sheet: BulkImportSheetPreview) {
    const next = { ...this.importMapping() };
    Object.entries(sheet.suggested_mapping || {}).forEach(([raw, field]) => {
      if (field) next[raw] = field;
      else delete next[raw];
    });
    this.importMapping.set(next);
  }

  resetMappingToSuggested() {
    this.importMapping.set({});
    this.seedMappingFromAllPreviews();
    this.activePresetId.set('');
  }

  clearMapping() {
    this.importMapping.set({});
    this.activePresetId.set('');
  }

  // -------------------- Mapping presets --------------------
  openSavePreset() {
    this.newPresetName = '';
    this.showSavePresetForm.set(true);
  }

  savePreset() {
    const name = (this.newPresetName || '').trim();
    if (!name) return;
    const preset: MappingPreset = {
      id: `p_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      name,
      createdAt: new Date().toISOString(),
      mapping: { ...this.importMapping() },
    };
    this.presets.set([preset, ...this.presets()]);
    this.activePresetId.set(preset.id);
    this.showSavePresetForm.set(false);
    this.newPresetName = '';
  }

  applyPreset(id: string) {
    this.activePresetId.set(id);
    if (!id) return;
    const preset = this.presets().find((p) => p.id === id);
    if (preset) this.importMapping.set({ ...preset.mapping });
  }

  deleteActivePreset() {
    const id = this.activePresetId();
    if (!id) return;
    this.presets.set(this.presets().filter((p) => p.id !== id));
    this.activePresetId.set('');
  }

  // -------------------- Totals (review step) --------------------
  totalRowsForFile(entry: FilePreviewEntry): number {
    return entry.preview?.sheets.reduce((s, sh) => s + (sh.row_count_estimate || 0), 0) || 0;
  }

  // -------------------- Import execution --------------------
  quickImport() {
    const files = this.files().map((e) => e.file);
    if (files.length === 0) return;
    this.runImport(files, undefined);
  }

  runImportFromReview() {
    const files = this.files().map((e) => e.file);
    if (files.length === 0) return;
    const mapping = Object.keys(this.importMapping()).length > 0 ? this.importMapping() : undefined;
    this.runImport(files, mapping);
  }

  private runImport(files: File[], mapping?: { [raw: string]: string }) {
    this.isImporting.set(true);
    this.importError.set(null);
    this.bulkImport.import(this.target(), files, mapping, this.strategy()).subscribe({
      next: (result) => {
        this.importResult.set(result);
        this.isImporting.set(false);
        this.step.set('result');
        this.pushHistory(result, files);
      },
      error: (err) => {
        this.importError.set(this.formatError(err));
        this.isImporting.set(false);
      },
    });
  }

  private pushHistory(result: BulkImportResult, files: File[]) {
    const entry: ImportHistoryEntry = {
      at: new Date().toLocaleString(),
      files: files.map((f) => f.name),
      totals: {
        created: result.totals.created || 0,
        updated: result.totals.updated || 0,
        skipped: result.totals.skipped || 0,
        failed: result.totals.failed || 0,
      },
      strategy: this.strategy(),
      target: this.target(),
    };
    this.history.set([entry, ...this.history()].slice(0, HISTORY_LIMIT));
  }

  clearHistory() {
    this.history.set([]);
  }

  startOver() {
    this.files.set([]);
    this.importMapping.set({});
    this.importResult.set(null);
    this.importError.set(null);
    this.activeFileIndex.set(0);
    this.activeSheetIndex.set(0);
    this.activePresetId.set('');
    this.strategy.set('skip');
    this.step.set('upload');
  }

  downloadErrorsCsv(file: BulkImportFileResult) {
    if (!isPlatformBrowser(this.platformId)) return;
    const header = ['file', 'sheet', 'row', 'id', 'error'];
    const rows = file.errors.map((e) => [
      file.file,
      e.sheet ?? '',
      e.row != null ? String(e.row) : '',
      e.id ?? '',
      (e.error ?? '').replace(/\r?\n/g, ' '),
    ]);
    const csv = [header, ...rows]
      .map((r) =>
        r
          .map((cell) => {
            const s = String(cell ?? '');
            return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
          })
          .join(','),
      )
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${file.file.replace(/\.[^.]+$/, '')}-import-errors.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // -------------------- Utilities --------------------
  private mutateFiles(mutator: (arr: FilePreviewEntry[]) => void) {
    const next = this.files().slice();
    mutator(next);
    this.files.set(next);
  }

  private formatError(err: any): string {
    if (!err) return 'Unknown error';
    if (err.error?.message) return err.error.message;
    if (err.error?.error) return err.error.error;
    if (err.message) return err.message;
    return 'Request failed';
  }

  private fallbackFields(target: ImportTarget): string[] {
    switch (target) {
      case 'specifications':
        return ['spec_id', 'title', 'description', 'category', 'version', 'status', 'file_url'];
      case 'requirements':
        return [
          'requirement_id',
          'title',
          'description',
          'requirement_type',
          'given',
          'when_action',
          'then_result',
          'priority',
          'status',
          'assignee',
          'tags',
        ];
      case 'design_tickets':
        return [
          'design_ticket_id',
          'title',
          'description',
          'design_type',
          'diagram_type',
          'image_url',
          'priority',
          'status',
          'linked_requirement_id',
          'assignee',
          'tags',
        ];
      case 'test_cases':
        return [
          'test_case_id',
          'title',
          'description',
          'vehicle_model',
          'severity',
          'feature',
          'priority',
          'test_type',
          'region',
          'brand',
          'vehicle_variant',
          'vehicle_specification',
          'env_dependency',
          'test_objective',
          'preconditions',
          'procedure',
          'expected_behavior',
          'associated_requirement_id',
          'screen_id',
          'reference_document',
          'requirement_type',
          'regulation',
          'testsuite_type',
        ];
    }
  }

  private fallbackRequired(target: ImportTarget): string[] {
    switch (target) {
      case 'specifications':
        return ['spec_id', 'title'];
      case 'requirements':
        return ['requirement_id', 'title'];
      case 'design_tickets':
        return ['design_ticket_id', 'title'];
      case 'test_cases':
        return ['test_case_id'];
    }
  }
}
