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
import { Router, RouterModule } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import {
  TestCaseImportDuplicateStrategy,
  TestCaseImportFileResult,
  TestCaseImportPreview,
  TestCaseImportResult,
  TestCaseImportSheetPreview,
  TestCaseService,
} from '../services/test-case.service';

/**
 * Per-file preview cache. Keyed by file index so the user can flip
 * between uploaded workbooks without re-uploading anything.
 */
interface FilePreviewEntry {
  file: File;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error: string | null;
  preview: TestCaseImportPreview | null;
}

/**
 * Saved mapping recipe. Persisted to localStorage so users can apply
 * the same column → field mapping across recurring vendor exports.
 */
interface MappingPreset {
  id: string;
  name: string;
  createdAt: string;
  mapping: { [rawHeader: string]: string };
}

/** A row in the recent-imports history strip. */
interface ImportHistoryEntry {
  at: string;
  files: string[];
  totals: { created: number; updated: number; skipped: number; failed: number };
  strategy: TestCaseImportDuplicateStrategy;
}

type WizardStep = 'upload' | 'map' | 'review' | 'result';

const PRESETS_KEY = 'sakura.tc-import.presets.v1';
const HISTORY_KEY = 'sakura.tc-import.history.v1';
const MAPPING_KEY = 'sakura.tc-import.active-mapping.v1';
const HISTORY_LIMIT = 8;

@Component({
  selector: 'app-import-test-cases',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
  <div class="import-page">
    <header class="page-header">
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <a routerLink="/" class="crumb">Dashboard</a>
        <span class="sep">/</span>
        <a routerLink="/test-cases" class="crumb">Test cases</a>
        <span class="sep">/</span>
        <span class="crumb current">Import</span>
      </nav>
      <div class="title-row">
        <div>
          <h1>Import test cases</h1>
          <p class="lead">
            Bulk-load from Excel or CSV. Map columns once, save as a preset, and reuse it across files.
          </p>
        </div>
        <button type="button" class="btn ghost subtle" (click)="goBack()">Cancel</button>
      </div>
    </header>

    <!-- Minimal stepper -->
    <ol class="stepper" role="tablist">
      <li *ngFor="let s of steps; let i = index"
          [class.active]="step() === s.id"
          [class.done]="stepIndex(s.id) < stepIndex(step())"
          (click)="jumpToStep(s.id)"
          role="tab">
        <span class="dot"></span>
        <span class="label">{{ s.label }}</span>
      </li>
    </ol>

    <!-- ============================================================== -->
    <!-- STEP 1 · UPLOAD                                                 -->
    <!-- ============================================================== -->
    <section class="card" *ngIf="step() === 'upload'">
      <div
        class="dropzone"
        [class.dragging]="isDragging()"
        [class.compact]="files().length > 0"
        (dragover)="onDragOver($event)"
        (dragleave)="onDragLeave($event)"
        (drop)="onDrop($event)"
        (click)="fileInput.click()">
        <input
          type="file"
          multiple
          accept=".xlsx,.xlsm,.csv"
          (change)="onFileInputChange($event)"
          #fileInput
          hidden>
        <div class="dz-content">
          <h3>{{ files().length > 0 ? 'Add more files' : 'Drop files here' }}</h3>
          <p class="muted">
            <ng-container *ngIf="files().length === 0">or click to browse — </ng-container>
            .xlsx, .xlsm, .csv
          </p>
        </div>
      </div>

      <div class="file-list" *ngIf="files().length > 0">
        <header>
          <span>{{ files().length }} file<ng-container *ngIf="files().length !== 1">s</ng-container></span>
          <button type="button" class="link subtle" (click)="clearFiles()">Clear all</button>
        </header>
        <ul>
          <li *ngFor="let entry of files(); let i = index">
            <span class="fname" [title]="entry.file.name">{{ entry.file.name }}</span>
            <span class="fmeta">{{ formatBytes(entry.file.size) }}</span>
            <span class="fstatus" [class]="'st-' + entry.status">
              <ng-container [ngSwitch]="entry.status">
                <ng-container *ngSwitchCase="'idle'">Queued</ng-container>
                <ng-container *ngSwitchCase="'loading'"><span class="spinner-xs"></span>Reading</ng-container>
                <ng-container *ngSwitchCase="'ready'">{{ sheetCountFor(entry) }} sheet<ng-container *ngIf="sheetCountFor(entry) !== 1">s</ng-container></ng-container>
                <ng-container *ngSwitchCase="'error'">Failed</ng-container>
              </ng-container>
            </span>
            <button type="button" class="icon-btn" (click)="removeFile(i); $event.stopPropagation()" aria-label="Remove">×</button>
          </li>
        </ul>
      </div>

      <details class="hints" *ngIf="files().length === 0">
        <summary>What works best</summary>
        <ul>
          <li>One header row per sheet.</li>
          <li>First sheet is auto-targeted (loose names like <code>Tests</code>, <code>TC</code> work).</li>
          <li>Required: <code>test_case_id</code> — auto-generated if omitted.</li>
          <li>~10,000 rows per workbook is comfortable; larger still works.</li>
        </ul>
      </details>

      <div class="actions-bar">
        <span class="muted" *ngIf="files().length > 0">
          {{ readyCount() }} of {{ files().length }} previewed
        </span>
        <div class="grow"></div>
        <button
          type="button"
          class="btn ghost"
          [disabled]="files().length === 0 || isImporting()"
          (click)="quickImport()"
          title="Skip mapping and trust auto-detection.">
          Quick import
        </button>
        <button
          type="button"
          class="btn primary"
          [disabled]="files().length === 0 || isPreviewingAny()"
          (click)="goToMap()">
          <span *ngIf="isPreviewingAny()" class="spinner-xs"></span>
          {{ isPreviewingAny() ? 'Reading…' : 'Continue' }}
        </button>
      </div>
    </section>

    <!-- ============================================================== -->
    <!-- STEP 2 · MAPPING                                                -->
    <!-- ============================================================== -->
    <section class="card" *ngIf="step() === 'map'">
      <!-- File tabs (one tab per uploaded workbook) -->
      <div class="file-tabs" *ngIf="files().length > 1">
        <button
          *ngFor="let entry of files(); let i = index"
          type="button"
          class="file-tab"
          [class.active]="activeFileIndex() === i"
          [class.has-error]="entry.status === 'error'"
          (click)="setActiveFile(i)">
          <span class="tab-name">{{ entry.file.name }}</span>
        </button>
      </div>

      <ng-container *ngIf="activeEntry() as entry">
        <div class="loading-row" *ngIf="entry.status === 'loading'">
          <span class="spinner"></span> Parsing <strong>{{ entry.file.name }}</strong>…
        </div>
        <div class="error-row" *ngIf="entry.status === 'error'">
          <span>{{ entry.error }}</span>
          <button type="button" class="btn small" (click)="previewFile(activeFileIndex())">Retry</button>
        </div>

        <ng-container *ngIf="entry.status === 'ready' && entry.preview as preview">
          <!-- Sheet picker -->
          <div class="sheet-picker" *ngIf="preview.sheets.length > 1">
            <button
              *ngFor="let s of preview.sheets; let si = index"
              type="button"
              class="sheet-pill"
              [class.active]="activeSheetIndex() === si"
              (click)="activeSheetIndex.set(si)">
              {{ s.sheet }} <span class="pill-meta">· {{ s.row_count_estimate }} rows</span>
            </button>
          </div>

          <ng-container *ngIf="preview.sheets[activeSheetIndex()] as sheet">
            <!-- Single calm summary row -->
            <div class="map-toolbar">
              <div class="summary-line">
                <strong>{{ mappedColumnCount(sheet) }}</strong>
                <span class="muted"> of {{ sheet.raw_headers.length }} columns mapped</span>
                <span class="dot-sep" *ngIf="missingRequired(sheet).length > 0">·</span>
                <span class="warn-inline" *ngIf="missingRequired(sheet).length > 0">
                  Missing: {{ missingRequired(sheet).join(', ') }}
                </span>
                <span class="dot-sep" *ngIf="missingRequired(sheet).length === 0 && mappedColumnCount(sheet) > 0">·</span>
                <span class="ok-inline" *ngIf="missingRequired(sheet).length === 0 && mappedColumnCount(sheet) > 0">
                  All required fields covered
                </span>
              </div>
              <input
                type="search"
                class="mapping-search"
                placeholder="Filter columns"
                [(ngModel)]="mappingFilter">
              <button type="button" class="link subtle"
                      (click)="showAdvancedMapping.set(!showAdvancedMapping())">
                {{ showAdvancedMapping() ? 'Hide options' : 'Options' }}
              </button>
            </div>

            <!-- Collapsible advanced toolbar: presets + bulk ops -->
            <div class="advanced-bar" *ngIf="showAdvancedMapping()">
              <div class="row">
                <label class="field">
                  <span>Preset</span>
                  <select [ngModel]="activePresetId()" (ngModelChange)="applyPreset($event)">
                    <option [ngValue]="''">None</option>
                    <option *ngFor="let p of presets()" [ngValue]="p.id">{{ p.name }}</option>
                  </select>
                </label>
                <button type="button" class="btn small ghost" (click)="openSavePreset()">Save as preset</button>
                <button type="button" class="btn small ghost"
                        [disabled]="!activePresetId()"
                        (click)="deleteActivePreset()">Delete preset</button>
              </div>
              <div class="row">
                <span class="muted small">Bulk</span>
                <button type="button" class="btn small ghost" (click)="setAllToIgnore(sheet)">Ignore all in sheet</button>
                <button type="button" class="btn small ghost" (click)="applySuggestionForSheet(sheet)">Restore suggestions</button>
                <button type="button" class="btn small ghost" (click)="resetMappingToSuggested()">Reset everything</button>
                <button type="button" class="btn small ghost" (click)="clearMapping()">Clear all</button>
              </div>
            </div>

            <!-- Inline save-preset form -->
            <div class="inline-form" *ngIf="showSavePresetForm()">
              <input
                type="text"
                placeholder="Preset name"
                [(ngModel)]="newPresetName"
                (keyup.enter)="savePreset()">
              <button type="button" class="btn small primary" (click)="savePreset()">Save</button>
              <button type="button" class="btn small ghost" (click)="showSavePresetForm.set(false)">Cancel</button>
            </div>

            <!-- Mapping table -->
            <div class="table-wrap">
              <table class="mapping-table">
                <thead>
                  <tr>
                    <th>Spreadsheet column</th>
                    <th>Sample</th>
                    <th>Maps to</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let header of filteredHeaders(sheet); let i = index"
                      [class.unmapped]="!getMappingValue(header)">
                    <td>
                      <code>{{ header }}</code>
                      <span class="req-mark" *ngIf="isRequiredHeader(header)" title="Required field">*</span>
                    </td>
                    <td class="sample-cell">{{ sampleValueFor(sheet, headerIndex(sheet, header)) || '—' }}</td>
                    <td>
                      <select
                        class="map-select"
                        [value]="getMappingValue(header)"
                        (change)="setMappingValue(header, $any($event.target).value)">
                        <option value="">Ignore</option>
                        <option *ngFor="let f of importFields()" [value]="f">
                          {{ f }}{{ isRequired(f) ? ' *' : '' }}
                        </option>
                      </select>
                    </td>
                  </tr>
                  <tr *ngIf="filteredHeaders(sheet).length === 0">
                    <td colspan="3" class="muted center">No columns match.</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Live sample preview with mapping applied -->
            <details class="sample-preview">
              <summary>Preview first {{ previewSampleCount(sheet) }} rows</summary>
              <div class="sample-table-wrap">
                <table class="sample-table">
                  <thead>
                    <tr>
                      <th *ngFor="let col of mappedColumns(sheet)">{{ col.field }}</th>
                      <th *ngIf="mappedColumns(sheet).length === 0" class="muted">No fields mapped yet</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr *ngFor="let row of sheet.sample_rows">
                      <td *ngFor="let col of mappedColumns(sheet)">{{ row[col.index] ?? '' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </details>
          </ng-container>
        </ng-container>
      </ng-container>

      <div class="actions-bar sticky">
        <button type="button" class="btn ghost" (click)="step.set('upload')">Back</button>
        <div class="grow"></div>
        <button type="button" class="btn primary" (click)="step.set('review')"
                [disabled]="!hasAnyReadyPreview()">
          Continue
        </button>
      </div>
    </section>

    <!-- ============================================================== -->
    <!-- STEP 3 · REVIEW                                                 -->
    <!-- ============================================================== -->
    <section class="card" *ngIf="step() === 'review'">
      <div class="totals-row">
        <div class="kpi">
          <span class="k-label">Files</span><strong>{{ files().length }}</strong>
        </div>
        <div class="kpi">
          <span class="k-label">Sheets</span><strong>{{ totalSheets() }}</strong>
        </div>
        <div class="kpi">
          <span class="k-label">Rows</span><strong>{{ totalRows() }}</strong>
        </div>
        <div class="kpi">
          <span class="k-label">Mapped columns</span><strong>{{ totalMappedColumns() }}</strong>
        </div>
      </div>

      <div class="review-cols">
        <section class="rev-block">
          <h4>Files</h4>
          <ul class="dense-list">
            <li *ngFor="let entry of files()">
              <span class="fname">{{ entry.file.name }}</span>
              <span class="muted">
                {{ formatBytes(entry.file.size) }}<ng-container *ngIf="entry.preview">
                · {{ entry.preview.sheets.length }} sheet<ng-container *ngIf="entry.preview.sheets.length !== 1">s</ng-container>
                · {{ totalRowsForFile(entry) }} rows
                </ng-container>
              </span>
            </li>
          </ul>
        </section>

        <section class="rev-block">
          <h4>Duplicate strategy</h4>
          <label class="radio" [class.checked]="strategy() === 'skip'">
            <input type="radio" name="dup" [checked]="strategy() === 'skip'" (change)="strategy.set('skip')">
            <div>
              <strong>Skip</strong>
              <div class="muted">Leave existing rows untouched.</div>
            </div>
          </label>
          <label class="radio" [class.checked]="strategy() === 'replace'">
            <input type="radio" name="dup" [checked]="strategy() === 'replace'" (change)="strategy.set('replace')">
            <div>
              <strong>Replace</strong>
              <div class="muted">Update existing rows in place.</div>
            </div>
          </label>
        </section>
      </div>

      <section class="rev-block warn" *ngIf="mappingWarnings().length > 0">
        <h4>Heads-up</h4>
        <ul class="dense-list">
          <li *ngFor="let w of mappingWarnings()">{{ w }}</li>
        </ul>
      </section>

      <p class="import-error" *ngIf="importError()">{{ importError() }}</p>

      <div class="actions-bar sticky">
        <button type="button" class="btn ghost" (click)="step.set('map')">Back</button>
        <div class="grow"></div>
        <button
          type="button"
          class="btn primary"
          [disabled]="isImporting() || files().length === 0"
          (click)="runImportFromReview()">
          <span *ngIf="isImporting()" class="spinner-xs"></span>
          {{ isImporting() ? 'Importing…' : 'Import ' + files().length + ' file' + (files().length !== 1 ? 's' : '') }}
        </button>
      </div>
    </section>

    <!-- ============================================================== -->
    <!-- STEP 4 · RESULT                                                 -->
    <!-- ============================================================== -->
    <section class="card" *ngIf="step() === 'result' && importResult() as result">
      <div class="result-pills">
        <div class="pill"><span class="pill-num">{{ result.totals.created }}</span><span class="pill-label">Created</span></div>
        <div class="pill"><span class="pill-num">{{ result.totals.updated || 0 }}</span><span class="pill-label">Updated</span></div>
        <div class="pill"><span class="pill-num">{{ result.totals.skipped }}</span><span class="pill-label">Skipped</span></div>
        <div class="pill" [class.has-fails]="result.totals.failed > 0">
          <span class="pill-num">{{ result.totals.failed }}</span><span class="pill-label">Failed</span>
        </div>
      </div>

      <div class="per-file-results">
        <div *ngFor="let file of result.files" class="file-result">
          <header>
            <h4>{{ file.file }}</h4>
            <span class="muted">
              {{ file.created }} created · {{ file.updated || 0 }} updated · {{ file.skipped }} skipped · {{ file.failed }} failed
            </span>
          </header>
          <table class="sheet-result-table" *ngIf="file.sheets.length > 0">
            <thead>
              <tr>
                <th>Sheet</th><th>Target</th>
                <th>Created</th><th>Updated</th><th>Skipped</th><th>Failed</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let s of file.sheets">
                <td>{{ s.sheet }}</td>
                <td><code>{{ s.target }}</code></td>
                <td>{{ s.created }}</td>
                <td>{{ s.updated || 0 }}</td>
                <td>{{ s.skipped }}</td>
                <td [class.has-fails]="s.failed > 0">{{ s.failed }}</td>
              </tr>
            </tbody>
          </table>
          <details *ngIf="file.errors.length > 0" class="errors-block">
            <summary>
              {{ file.errors.length }} error row<ng-container *ngIf="file.errors.length !== 1">s</ng-container>
              <button type="button" class="link" (click)="downloadErrorsCsv(file); $event.preventDefault(); $event.stopPropagation()">
                Download CSV
              </button>
            </summary>
            <ul class="error-list">
              <li *ngFor="let err of file.errors.slice(0, 50)">
                <ng-container *ngIf="err.sheet">[{{ err.sheet }}] </ng-container>
                <ng-container *ngIf="err.row">Row {{ err.row }}: </ng-container>
                <ng-container *ngIf="err.id"><code>{{ err.id }}</code> — </ng-container>
                {{ err.error }}
              </li>
              <li *ngIf="file.errors.length > 50" class="muted">
                … and {{ file.errors.length - 50 }} more (see CSV).
              </li>
            </ul>
          </details>
        </div>
      </div>

      <div class="actions-bar sticky">
        <button type="button" class="btn ghost" (click)="startOver()">Import more</button>
        <div class="grow"></div>
        <a routerLink="/test-cases" class="btn primary">View test cases</a>
      </div>
    </section>

    <!-- ============================================================== -->
    <!-- Recent imports — quiet, low-emphasis                             -->
    <!-- ============================================================== -->
    <section class="history-strip" *ngIf="history().length > 0 && step() !== 'result'">
      <header>
        <h3>Recent</h3>
        <button type="button" class="link subtle" (click)="clearHistory()">Clear</button>
      </header>
      <ul>
        <li *ngFor="let h of history()">
          <span class="h-time">{{ h.at }}</span>
          <span class="h-files muted" [title]="h.files.join('\n')">
            {{ h.files.length }} file<ng-container *ngIf="h.files.length !== 1">s</ng-container>
          </span>
          <span class="h-num">+{{ h.totals.created }}</span>
          <span class="h-num muted">~{{ h.totals.updated }}</span>
          <span class="h-num muted">·{{ h.totals.skipped }}</span>
          <span class="h-num danger" *ngIf="h.totals.failed > 0">!{{ h.totals.failed }}</span>
          <span class="h-strategy muted">{{ h.strategy }}</span>
        </li>
      </ul>
    </section>
  </div>
  `,
  styles: [`
    /* =========================================================
       Design tokens — calm neutrals + a single accent.
       Type scale: 12 / 13 / 14 / 15 / 22.
       ========================================================= */
    :host {
      display:block;
      --c-fg:        #0f172a;
      --c-fg-soft:   #334155;
      --c-muted:     #64748b;
      --c-muted-2:   #94a3b8;
      --c-border:    #e2e8f0;
      --c-border-strong: #cbd5e1;
      --c-bg:        #f8fafc;
      --c-card:      #ffffff;
      --c-accent:    #2563eb;
      --c-accent-soft:#eff6ff;
      --c-danger:    #b91c1c;
      --c-danger-soft:#fef2f2;
      --c-ok:        #15803d;
      --c-warn-fg:   #92400e;
      --c-warn-bg:   #fffbeb;
      --radius:      8px;
      --radius-lg:   12px;
      --shadow-1:    0 1px 2px rgba(15,23,42,.04);
    }
    .import-page {
      max-width: 1080px;
      margin: 0 auto;
      padding: 28px 28px 96px;
      color: var(--c-fg);
      font: 400 14px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
      font-feature-settings: "cv11", "ss01";
      -webkit-font-smoothing: antialiased;
      letter-spacing: -0.005em;
    }

    /* ---- Header ---- */
    .page-header { margin-bottom: 24px; }
    .breadcrumb { font-size: 12px; color: var(--c-muted); margin-bottom: 12px;
                  letter-spacing: 0; }
    .breadcrumb .crumb { color: var(--c-muted); text-decoration: none; }
    .breadcrumb .crumb:hover { color: var(--c-accent); }
    .breadcrumb .crumb.current { color: var(--c-fg); font-weight: 500; }
    .breadcrumb .sep { margin: 0 8px; color: var(--c-muted-2); }

    .title-row { display: flex; align-items: flex-start; gap: 16px; }
    .title-row > div:first-child { flex: 1; }
    .title-row h1 { font-size: 22px; line-height: 1.2; font-weight: 600;
                    margin: 0; letter-spacing: -0.02em; }
    .lead { color: var(--c-muted); margin: 6px 0 0; max-width: 640px;
            font-size: 14px; line-height: 1.55; }

    /* ---- Stepper — minimal dots + label ---- */
    .stepper { list-style: none; padding: 0; margin: 0 0 20px;
               display: flex; gap: 0; align-items: center; }
    .stepper li { display: inline-flex; align-items: center; gap: 8px;
                  padding: 6px 14px 6px 8px; color: var(--c-muted);
                  cursor: pointer; font-size: 13px; font-weight: 500;
                  border-radius: 999px;
                  transition: color .12s, background .12s; }
    .stepper li:hover { color: var(--c-fg); }
    .stepper li.active { color: var(--c-fg); background: var(--c-accent-soft); }
    .stepper li.done { color: var(--c-fg-soft); }
    .stepper li .dot { width: 8px; height: 8px; border-radius: 50%;
                       background: var(--c-border-strong); flex-shrink: 0; }
    .stepper li.active .dot { background: var(--c-accent); }
    .stepper li.done .dot { background: var(--c-ok); }
    .stepper li + li::before { content: ""; width: 16px; height: 1px;
                               background: var(--c-border); margin: 0 4px;
                               display: inline-block; }

    /* ---- Cards ---- */
    .card { background: var(--c-card);
            border: 1px solid var(--c-border);
            border-radius: var(--radius-lg);
            padding: 24px;
            box-shadow: var(--shadow-1);
            margin-bottom: 16px; }

    .muted { color: var(--c-muted); }
    .center { text-align: center; }
    .grow { flex: 1; }
    code { font: 12px/1.4 ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
           background: #f1f5f9; padding: 1px 6px; border-radius: 4px;
           color: var(--c-fg-soft); letter-spacing: 0; }

    /* ---- Dropzone ---- */
    .dropzone { border: 1.5px dashed var(--c-border-strong);
                border-radius: var(--radius-lg); padding: 48px 24px;
                text-align: center; cursor: pointer; background: var(--c-bg);
                transition: border-color .15s, background .15s; }
    .dropzone:hover,
    .dropzone.dragging { border-color: var(--c-accent);
                         background: var(--c-accent-soft); }
    .dropzone.compact { padding: 24px; }
    .dz-content h3 { margin: 0 0 4px; font-size: 15px; font-weight: 600;
                     color: var(--c-fg); letter-spacing: -0.01em; }
    .dz-content p { margin: 0; font-size: 13px; }

    /* ---- File list ---- */
    .file-list { margin-top: 16px; border: 1px solid var(--c-border);
                 border-radius: var(--radius); overflow: hidden; background: #fff; }
    .file-list > header { display: flex; align-items: center; justify-content: space-between;
                          padding: 10px 16px; background: var(--c-bg);
                          border-bottom: 1px solid var(--c-border);
                          font-size: 13px; color: var(--c-fg-soft); }
    .file-list ul { list-style: none; padding: 0; margin: 0; }
    .file-list li { display: grid;
                    grid-template-columns: 1fr auto auto 28px;
                    gap: 16px; align-items: center;
                    padding: 10px 16px; border-bottom: 1px solid var(--c-border);
                    font-size: 13px; }
    .file-list li:last-child { border-bottom: none; }
    .fname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
             color: var(--c-fg); }
    .fmeta { color: var(--c-muted); font-variant-numeric: tabular-nums; font-size: 12px; }
    .fstatus { font-size: 12px; color: var(--c-muted); display: inline-flex; align-items: center; gap: 4px; }
    .fstatus.st-ready { color: var(--c-ok); }
    .fstatus.st-error { color: var(--c-danger); }

    /* ---- Hints (collapsed by default) ---- */
    .hints { margin-top: 16px; font-size: 13px; }
    .hints summary { cursor: pointer; color: var(--c-muted); font-weight: 500;
                     padding: 6px 0; outline: none; }
    .hints summary:hover { color: var(--c-fg); }
    .hints ul { margin: 8px 0 0; padding-left: 20px; color: var(--c-muted); }
    .hints li { padding: 2px 0; }

    /* ---- Action bar ---- */
    .actions-bar { display: flex; align-items: center; gap: 8px;
                   margin-top: 24px; padding-top: 16px;
                   border-top: 1px solid var(--c-border); }
    .actions-bar.sticky { position: sticky; bottom: 0;
                          background: linear-gradient(to top, #fff 80%, rgba(255,255,255,0));
                          margin-left: -24px; margin-right: -24px;
                          padding: 16px 24px 4px; }

    /* ---- Buttons ---- */
    .btn { display: inline-flex; align-items: center; gap: 6px;
           padding: 7px 14px; border: 1px solid var(--c-border-strong);
           background: #fff; border-radius: 6px; cursor: pointer;
           font: 500 13px/1.2 inherit; color: var(--c-fg);
           transition: background .12s, border-color .12s, color .12s;
           letter-spacing: -0.005em; }
    .btn:hover:not(:disabled) { background: var(--c-bg); border-color: var(--c-fg-soft); }
    .btn:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }
    .btn:disabled { opacity: .5; cursor: not-allowed; }
    .btn.primary { background: var(--c-accent); color: #fff; border-color: var(--c-accent); }
    .btn.primary:hover:not(:disabled) { background: #1d4ed8; border-color: #1d4ed8; }
    .btn.ghost { background: transparent; border-color: var(--c-border); color: var(--c-fg-soft); }
    .btn.ghost:hover:not(:disabled) { color: var(--c-fg); background: var(--c-bg); }
    .btn.ghost.subtle { border-color: transparent; }
    .btn.small { padding: 5px 10px; font-size: 12px; }
    .icon-btn { background: transparent; border: none; cursor: pointer;
                color: var(--c-muted-2); font-size: 18px; line-height: 1;
                width: 28px; height: 28px; border-radius: 4px;
                display: inline-grid; place-items: center; }
    .icon-btn:hover { color: var(--c-danger); background: var(--c-danger-soft); }
    .link { background: transparent; border: none; color: var(--c-accent);
            cursor: pointer; font: inherit; font-size: 12px; padding: 0;
            text-decoration: none; }
    .link:hover { text-decoration: underline; }
    .link.subtle { color: var(--c-muted); }
    .link.subtle:hover { color: var(--c-fg); }
    .link.danger { color: var(--c-danger); }

    /* ---- Spinner ---- */
    .spinner, .spinner-xs {
      display: inline-block; border: 2px solid var(--c-border-strong);
      border-top-color: var(--c-accent); border-radius: 50%;
      animation: spin .7s linear infinite;
    }
    .spinner { width: 16px; height: 16px; }
    .spinner-xs { width: 10px; height: 10px; border-width: 1.5px;
                  margin-right: 4px; vertical-align: -1px; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ---- File tabs (multi-file) ---- */
    .file-tabs { display: flex; gap: 4px; overflow-x: auto;
                 border-bottom: 1px solid var(--c-border);
                 margin: -8px -8px 20px; padding: 0 8px; }
    .file-tab { padding: 10px 14px; border: none; background: transparent;
                cursor: pointer; border-bottom: 2px solid transparent;
                margin-bottom: -1px; color: var(--c-muted);
                font: 500 13px inherit; white-space: nowrap;
                transition: color .12s, border-color .12s; }
    .file-tab:hover { color: var(--c-fg); }
    .file-tab.active { color: var(--c-fg); border-bottom-color: var(--c-accent); }
    .file-tab.has-error { color: var(--c-danger); }

    /* ---- Sheet picker ---- */
    .sheet-picker { display: flex; gap: 6px; align-items: center;
                    margin-bottom: 16px; flex-wrap: wrap; }
    .sheet-pill { padding: 4px 12px; border: 1px solid var(--c-border);
                  border-radius: 999px; background: #fff; cursor: pointer;
                  font: 500 12px inherit; color: var(--c-fg-soft);
                  transition: background .12s, border-color .12s, color .12s; }
    .sheet-pill:hover { background: var(--c-bg); border-color: var(--c-border-strong); }
    .sheet-pill.active { background: var(--c-fg); color: #fff; border-color: var(--c-fg); }
    .pill-meta { color: var(--c-muted); font-weight: 400; }
    .sheet-pill.active .pill-meta { color: rgba(255,255,255,.7); }

    /* ---- Mapping toolbar (single calm row) ---- */
    .map-toolbar { display: flex; align-items: center; gap: 12px;
                   margin-bottom: 12px; flex-wrap: wrap;
                   padding-bottom: 12px;
                   border-bottom: 1px solid var(--c-border); }
    .summary-line { flex: 1; font-size: 13px; color: var(--c-fg-soft);
                    min-width: 280px; }
    .summary-line strong { color: var(--c-fg); font-weight: 600;
                           font-variant-numeric: tabular-nums; }
    .dot-sep { color: var(--c-muted-2); margin: 0 6px; }
    .warn-inline { color: var(--c-warn-fg); }
    .ok-inline { color: var(--c-ok); }
    .mapping-search { padding: 6px 10px; border: 1px solid var(--c-border-strong);
                      border-radius: 6px; min-width: 180px; font: inherit;
                      font-size: 13px; color: var(--c-fg); }
    .mapping-search:focus { outline: none; border-color: var(--c-accent);
                            box-shadow: 0 0 0 3px var(--c-accent-soft); }

    /* ---- Advanced bar (presets + bulk ops, collapsible) ---- */
    .advanced-bar { background: var(--c-bg);
                    border: 1px solid var(--c-border);
                    border-radius: var(--radius);
                    padding: 12px 14px; margin-bottom: 12px;
                    display: flex; flex-direction: column; gap: 10px; }
    .advanced-bar .row { display: flex; gap: 8px; align-items: center;
                         flex-wrap: wrap; }
    .advanced-bar .field { display: inline-flex; align-items: center;
                           gap: 8px; font-size: 12px; color: var(--c-muted); }
    .advanced-bar select { padding: 5px 10px; border: 1px solid var(--c-border-strong);
                           border-radius: 6px; background: #fff;
                           font: 500 13px inherit; color: var(--c-fg); min-width: 180px; }
    .small { font-size: 12px; }

    .inline-form { display: flex; gap: 8px; margin-bottom: 12px; }
    .inline-form input { flex: 1; padding: 6px 10px;
                         border: 1px solid var(--c-border-strong);
                         border-radius: 6px; font: inherit; font-size: 13px; }
    .inline-form input:focus { outline: none; border-color: var(--c-accent);
                               box-shadow: 0 0 0 3px var(--c-accent-soft); }

    /* ---- Mapping table ---- */
    .table-wrap { border: 1px solid var(--c-border);
                  border-radius: var(--radius); overflow: hidden;
                  background: #fff; }
    .mapping-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .mapping-table th,
    .mapping-table td { padding: 9px 14px;
                        border-bottom: 1px solid var(--c-border);
                        text-align: left; vertical-align: middle; }
    .mapping-table tr:last-child td { border-bottom: none; }
    .mapping-table thead th { background: var(--c-bg);
                              font: 500 11px/1.2 inherit;
                              text-transform: uppercase;
                              letter-spacing: 0.05em;
                              color: var(--c-muted); }
    .mapping-table tbody tr:hover { background: var(--c-bg); }
    .mapping-table tr.unmapped td:first-child code { color: var(--c-muted-2); }
    .req-mark { color: var(--c-danger); margin-left: 4px; font-weight: 600; }
    .map-select { width: 100%; max-width: 240px; padding: 5px 10px;
                  border: 1px solid var(--c-border-strong); border-radius: 6px;
                  background: #fff; font: inherit; font-size: 13px;
                  color: var(--c-fg); }
    .map-select:focus { outline: none; border-color: var(--c-accent);
                        box-shadow: 0 0 0 3px var(--c-accent-soft); }
    .sample-cell { color: var(--c-muted); max-width: 240px;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
                   font-size: 12px; }

    /* ---- Sample preview ---- */
    .sample-preview { margin-top: 14px; border: 1px solid var(--c-border);
                      border-radius: var(--radius); padding: 12px 16px;
                      background: #fff; }
    .sample-preview summary { cursor: pointer; font-size: 13px;
                              font-weight: 500; color: var(--c-fg-soft);
                              outline: none; }
    .sample-preview summary:hover { color: var(--c-fg); }
    .sample-table-wrap { overflow: auto; margin-top: 12px;
                         max-height: 260px;
                         border: 1px solid var(--c-border); border-radius: 6px; }
    .sample-table { border-collapse: collapse; font-size: 12px;
                    min-width: 100%; }
    .sample-table th, .sample-table td {
      padding: 6px 12px; border-right: 1px solid var(--c-border);
      border-bottom: 1px solid var(--c-border);
      white-space: nowrap;
    }
    .sample-table th { background: var(--c-bg); font-weight: 500;
                       color: var(--c-fg-soft); position: sticky; top: 0;
                       text-align: left; }
    .sample-table td:last-child, .sample-table th:last-child { border-right: none; }

    /* ---- Review ---- */
    .totals-row { display: grid;
                  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                  gap: 1px; background: var(--c-border);
                  border: 1px solid var(--c-border); border-radius: var(--radius);
                  overflow: hidden; margin-bottom: 20px; }
    .kpi { display: flex; flex-direction: column; gap: 4px;
           background: #fff; padding: 14px 18px; }
    .kpi .k-label { font-size: 11px; color: var(--c-muted);
                    text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi strong { font-size: 22px; font-weight: 600;
                  font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }

    .review-cols { display: grid;
                   grid-template-columns: 1fr 1fr; gap: 20px;
                   margin-bottom: 16px; }
    @media (max-width: 720px) { .review-cols { grid-template-columns: 1fr; } }
    .rev-block h4 { margin: 0 0 10px; font-size: 12px;
                    text-transform: uppercase; letter-spacing: 0.06em;
                    color: var(--c-muted); font-weight: 600; }
    .rev-block.warn { background: var(--c-warn-bg);
                      border: 1px solid #fde68a; border-radius: var(--radius);
                      padding: 14px 16px; color: var(--c-warn-fg); }
    .rev-block.warn h4 { color: var(--c-warn-fg); }

    .dense-list { list-style: none; padding: 0; margin: 0; font-size: 13px; }
    .dense-list li { padding: 6px 0; border-bottom: 1px solid var(--c-border);
                     display: flex; gap: 10px; justify-content: space-between; }
    .dense-list li:last-child { border-bottom: none; }
    .rev-block.warn .dense-list li { border-color: rgba(146, 64, 14, 0.2); }

    .radio { display: flex; gap: 12px; align-items: flex-start;
             padding: 12px 14px; border: 1px solid var(--c-border);
             border-radius: var(--radius); background: #fff;
             margin-bottom: 8px; cursor: pointer;
             transition: border-color .12s, background .12s; }
    .radio:hover { border-color: var(--c-border-strong); }
    .radio.checked { border-color: var(--c-accent);
                     background: var(--c-accent-soft); }
    .radio input { margin-top: 3px; accent-color: var(--c-accent); }
    .radio strong { font-weight: 600; font-size: 13px; }
    .radio .muted { font-size: 12px; margin-top: 2px; }

    .import-error { background: var(--c-danger-soft); color: var(--c-danger);
                    border: 1px solid #fecaca; padding: 10px 14px;
                    border-radius: var(--radius); margin: 12px 0 0;
                    font-size: 13px; }

    /* ---- Result ---- */
    .result-pills { display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                    gap: 1px; background: var(--c-border);
                    border: 1px solid var(--c-border); border-radius: var(--radius);
                    overflow: hidden; margin-bottom: 24px; }
    .pill { background: #fff; padding: 18px 20px;
            display: flex; flex-direction: column; gap: 6px; }
    .pill-num { font-size: 26px; font-weight: 600;
                font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
    .pill-label { color: var(--c-muted); font-size: 11px;
                  text-transform: uppercase; letter-spacing: 0.06em; }
    .pill.has-fails .pill-num { color: var(--c-danger); }

    .per-file-results .file-result { border: 1px solid var(--c-border);
                                     border-radius: var(--radius); padding: 16px;
                                     margin-bottom: 12px; background: #fff; }
    .file-result header { display: flex; align-items: baseline; gap: 12px;
                          margin-bottom: 12px; flex-wrap: wrap; }
    .file-result h4 { margin: 0; font-size: 14px; font-weight: 600; }
    .sheet-result-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .sheet-result-table th, .sheet-result-table td {
      padding: 7px 12px; border-bottom: 1px solid var(--c-border);
      text-align: left;
    }
    .sheet-result-table thead th { color: var(--c-muted);
                                   text-transform: uppercase;
                                   letter-spacing: 0.05em;
                                   font-weight: 500; font-size: 11px; }
    .sheet-result-table .has-fails { color: var(--c-danger); font-weight: 600; }
    .errors-block { margin-top: 12px; padding: 10px 14px;
                    background: var(--c-bg); border: 1px solid var(--c-border);
                    border-radius: 6px; }
    .errors-block summary { display: flex; gap: 12px; align-items: center;
                            cursor: pointer; font-size: 13px;
                            color: var(--c-fg-soft); outline: none; }
    .errors-block summary > .link { margin-left: auto; }
    .error-list { margin: 10px 0 0; padding-left: 18px; font-size: 12px;
                  max-height: 240px; overflow-y: auto;
                  color: var(--c-fg-soft); }
    .error-list li { padding: 2px 0; }

    /* ---- Recent imports (very quiet) ---- */
    .history-strip { background: transparent;
                     border-top: 1px solid var(--c-border);
                     padding: 20px 0 0; margin-top: 24px; }
    .history-strip > header { display: flex; align-items: center;
                              justify-content: space-between; margin-bottom: 10px; }
    .history-strip h3 { margin: 0; font-size: 11px; color: var(--c-muted);
                        text-transform: uppercase; letter-spacing: 0.08em;
                        font-weight: 600; }
    .history-strip ul { list-style: none; padding: 0; margin: 0;
                        display: flex; flex-direction: column; gap: 2px; }
    .history-strip li { display: grid;
                        grid-template-columns: 170px 1fr auto auto auto auto auto;
                        gap: 12px; align-items: center; font-size: 12px;
                        padding: 6px 0; color: var(--c-fg-soft); }
    .h-time { color: var(--c-muted); font-variant-numeric: tabular-nums; }
    .h-num { font-variant-numeric: tabular-nums; font-weight: 500; }
    .h-num.danger { color: var(--c-danger); }
    .h-strategy { font-size: 10px; text-transform: uppercase;
                  letter-spacing: 0.08em; }

    .loading-row { padding: 16px; display: flex; gap: 12px;
                   align-items: center; color: var(--c-muted); font-size: 13px; }
    .error-row { padding: 12px 14px; background: var(--c-danger-soft);
                 color: var(--c-danger); border: 1px solid #fecaca;
                 border-radius: var(--radius);
                 display: flex; gap: 12px; align-items: center;
                 justify-content: space-between;
                 margin-bottom: 16px; font-size: 13px; }

    @media (max-width: 720px) {
      .import-page { padding: 20px 16px 80px; }
      .card { padding: 18px; }
      .stepper li .label { display: none; }
      .stepper li + li::before { width: 8px; }
      .title-row { flex-direction: column; }
    }
  `]
})
export class ImportTestCasesComponent implements OnInit {
  private testCaseService = inject(TestCaseService);
  private router = inject(Router);
  private location = inject(Location);
  private platformId = inject(PLATFORM_ID);

  // -------------------- Wizard state --------------------
  readonly steps: { id: WizardStep; label: string }[] = [
    { id: 'upload',  label: 'Upload' },
    { id: 'map',     label: 'Map columns' },
    { id: 'review',  label: 'Review' },
    { id: 'result',  label: 'Result' },
  ];
  step = signal<WizardStep>('upload');

  // -------------------- Files & previews --------------------
  files = signal<FilePreviewEntry[]>([]);
  isDragging = signal(false);
  activeFileIndex = signal(0);
  activeSheetIndex = signal(0);

  // -------------------- Mapping --------------------
  importFields = signal<string[]>([]);
  requiredFields = signal<string[]>(['test_case_id']);
  /** Effective raw-header → canonical-field mapping. Shared across files. */
  importMapping = signal<{ [rawHeader: string]: string }>({});
  mappingFilter = '';
  showAdvancedMapping = signal(false);
  showHints = signal(false);

  // -------------------- Presets / history (localStorage) --------------------
  presets = signal<MappingPreset[]>([]);
  activePresetId = signal<string>('');
  showSavePresetForm = signal(false);
  newPresetName = '';
  history = signal<ImportHistoryEntry[]>([]);

  // -------------------- Import execution --------------------
  strategy = signal<TestCaseImportDuplicateStrategy>('skip');
  isImporting = signal(false);
  importResult = signal<TestCaseImportResult | null>(null);
  importError = signal<string | null>(null);

  // -------------------- Derived --------------------
  readyCount = computed(() => this.files().filter(f => f.status === 'ready').length);
  isPreviewingAny = computed(() => this.files().some(f => f.status === 'loading'));
  activeEntry = computed<FilePreviewEntry | undefined>(() => this.files()[this.activeFileIndex()]);
  hasAnyReadyPreview = computed(() => this.files().some(f => f.status === 'ready'));

  totalSheets = computed(() =>
    this.files().reduce((sum, e) => sum + (e.preview?.sheets.length || 0), 0)
  );
  totalRows = computed(() =>
    this.files().reduce((sum, e) =>
      sum + (e.preview?.sheets.reduce((s, sh) => s + (sh.row_count_estimate || 0), 0) || 0), 0)
  );
  totalMappedColumns = computed(() => Object.keys(this.importMapping()).length);

  mappingWarnings = computed<string[]>(() => {
    const warnings: string[] = [];
    const mapped = new Set(Object.values(this.importMapping()));
    this.requiredFields().forEach(req => {
      if (!mapped.has(req)) {
        warnings.push(
          `Required field "${req}" is not mapped to any column. ` +
          `Rows without it will be auto-generated by the server.`
        );
      }
    });
    // Detect duplicate mapping targets (two columns → same field)
    const counts: Record<string, number> = {};
    Object.values(this.importMapping()).forEach(v => { counts[v] = (counts[v] || 0) + 1; });
    Object.entries(counts).forEach(([field, count]) => {
      if (count > 1) {
        warnings.push(`Field "${field}" is mapped from ${count} different columns — the last one wins.`);
      }
    });
    return warnings;
  });

  constructor() {
    // Persist presets / history whenever they change (browser only).
    effect(() => {
      const list = this.presets();
      if (isPlatformBrowser(this.platformId)) {
        try { localStorage.setItem(PRESETS_KEY, JSON.stringify(list)); } catch { /* quota — ignore */ }
      }
    });
    effect(() => {
      const list = this.history();
      if (isPlatformBrowser(this.platformId)) {
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(list)); } catch { /* quota — ignore */ }
      }
    });
    // Auto-save the active raw-header → field mapping the moment any dropdown
    // changes. Survives reloads & repeated imports of similar workbooks.
    effect(() => {
      const map = this.importMapping();
      if (!isPlatformBrowser(this.platformId)) return;
      try {
        if (Object.keys(map).length === 0) localStorage.removeItem(MAPPING_KEY);
        else localStorage.setItem(MAPPING_KEY, JSON.stringify(map));
      } catch { /* quota — ignore */ }
    });
  }

  ngOnInit(): void {
    // Pull the canonical field list once; fall back to a hard-coded list if
    // the backend is unreachable so the mapping UI still works.
    this.testCaseService.getImportFields().subscribe({
      next: res => {
        this.importFields.set(res.fields || []);
        if (res.required?.length) this.requiredFields.set(res.required);
      },
      error: () => {
        this.importFields.set([
          'test_case_id', 'title', 'description', 'vehicle_model', 'severity',
          'feature', 'priority', 'test_type', 'region', 'brand', 'vehicle_variant',
          'vehicle_specification', 'env_dependency', 'test_objective', 'preconditions',
          'procedure', 'expected_behavior', 'associated_requirement_id', 'screen_id',
          'reference_document', 'requirement_type', 'regulation', 'testsuite_type',
        ]);
      }
    });

    if (isPlatformBrowser(this.platformId)) {
      try {
        const raw = localStorage.getItem(PRESETS_KEY);
        if (raw) this.presets.set(JSON.parse(raw));
      } catch { /* corrupt JSON — reset silently */ }
      try {
        const raw = localStorage.getItem(HISTORY_KEY);
        if (raw) this.history.set(JSON.parse(raw));
      } catch { /* corrupt JSON — reset silently */ }
      try {
        const raw = localStorage.getItem(MAPPING_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === 'object') this.importMapping.set(parsed);
        }
      } catch { /* corrupt JSON — reset silently */ }
    }
  }

  // -------------------- Navigation helpers --------------------
  goBack() { this.location.back(); }

  stepIndex(s: WizardStep): number {
    return this.steps.findIndex(x => x.id === s);
  }

  jumpToStep(target: WizardStep) {
    if (target === 'result' && !this.importResult()) return;
    if (target === 'map'    && this.files().length === 0) return;
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
    const allowed = /\.(xlsx|xlsm|csv)$/i;
    const filtered = picked.filter(f => allowed.test(f.name));
    if (filtered.length === 0) {
      this.importError.set('No supported files. Use .xlsx, .xlsm, or .csv.');
      return;
    }
    this.importError.set(null);
    const existingNames = new Set(this.files().map(e => e.file.name + ':' + e.file.size));
    const additions: FilePreviewEntry[] = filtered
      .filter(f => !existingNames.has(f.name + ':' + f.size))
      .map(f => ({ file: f, status: 'idle' as const, error: null, preview: null }));
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
  /** Move to step 2, kicking off previews for any not-yet-previewed files. */
  goToMap() {
    const pending = this.files()
      .map((e, i) => ({ e, i }))
      .filter(x => x.e.status === 'idle' || x.e.status === 'error');

    if (pending.length === 0) {
      this.afterPreviewsSettled();
      return;
    }
    // Mark all pending as loading up-front so the UI shows progress immediately.
    this.mutateFiles(arr => pending.forEach(p => { arr[p.i] = { ...arr[p.i], status: 'loading', error: null }; }));

    const calls = pending.map(p =>
      this.testCaseService.previewImport(p.e.file).pipe(
        map(preview => ({ i: p.i, ok: true as const, preview })),
        catchError(err => of({ i: p.i, ok: false as const, error: this.formatError(err) }))
      )
    );
    forkJoin(calls).subscribe(results => {
      this.mutateFiles(arr => {
        results.forEach(r => {
          if (r.ok) arr[r.i] = { ...arr[r.i], status: 'ready', preview: r.preview, error: null };
          else      arr[r.i] = { ...arr[r.i], status: 'error', preview: null, error: r.error };
        });
      });
      this.afterPreviewsSettled();
    });
  }

  /** Re-preview a single file (e.g. after fixing the file). */
  previewFile(index: number) {
    const entry = this.files()[index];
    if (!entry) return;
    this.mutateFiles(arr => { arr[index] = { ...arr[index], status: 'loading', error: null }; });
    this.testCaseService.previewImport(entry.file).subscribe({
      next: preview => this.mutateFiles(arr => {
        arr[index] = { ...arr[index], status: 'ready', preview, error: null };
        this.seedMappingFromAllPreviews();
      }),
      error: err => this.mutateFiles(arr => {
        arr[index] = { ...arr[index], status: 'error', preview: null, error: this.formatError(err) };
      })
    });
  }

  private afterPreviewsSettled() {
    this.seedMappingFromAllPreviews();
    this.activeFileIndex.set(
      Math.max(0, this.files().findIndex(f => f.status === 'ready'))
    );
    this.activeSheetIndex.set(0);
    this.step.set('map');
  }

  /** Merge backend suggestions from every previewed sheet into one mapping. */
  private seedMappingFromAllPreviews() {
    const seed: { [raw: string]: string } = { ...this.importMapping() };
    this.files().forEach(entry => {
      entry.preview?.sheets.forEach(sheet => {
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

  filteredHeaders(sheet: TestCaseImportSheetPreview): string[] {
    const q = this.mappingFilter.trim().toLowerCase();
    if (!q) return sheet.raw_headers;
    return sheet.raw_headers.filter(h =>
      h.toLowerCase().includes(q) ||
      (this.getMappingValue(h) || '').toLowerCase().includes(q)
    );
  }

  headerIndex(sheet: TestCaseImportSheetPreview, header: string): number {
    return sheet.raw_headers.indexOf(header);
  }

  sampleValueFor(sheet: TestCaseImportSheetPreview, columnIndex: number): string | null {
    if (columnIndex < 0) return null;
    for (const row of sheet.sample_rows) {
      const v = row[columnIndex];
      if (v !== null && v !== undefined && String(v).trim() !== '') return String(v);
    }
    return null;
  }

  mappedColumnCount(sheet: TestCaseImportSheetPreview): number {
    return sheet.raw_headers.filter(h => this.getMappingValue(h)).length;
  }

  coverageRatio(sheet: TestCaseImportSheetPreview): number {
    if (sheet.raw_headers.length === 0) return 0;
    return this.mappedColumnCount(sheet) / sheet.raw_headers.length;
  }

  missingRequired(sheet: TestCaseImportSheetPreview): string[] {
    const mapped = new Set(sheet.raw_headers.map(h => this.getMappingValue(h)).filter(Boolean));
    return this.requiredFields().filter(req => !mapped.has(req));
  }

  mappedColumns(sheet: TestCaseImportSheetPreview): { index: number; field: string }[] {
    return sheet.raw_headers
      .map((h, i) => ({ index: i, field: this.getMappingValue(h) }))
      .filter(c => !!c.field);
  }

  previewSampleCount(sheet: TestCaseImportSheetPreview): number {
    return sheet.sample_rows?.length || 0;
  }

  // -------------------- Bulk mapping ops --------------------
  setAllToIgnore(sheet: TestCaseImportSheetPreview) {
    const next = { ...this.importMapping() };
    sheet.raw_headers.forEach(h => { delete next[h]; });
    this.importMapping.set(next);
  }

  applySuggestionForSheet(sheet: TestCaseImportSheetPreview) {
    const next = { ...this.importMapping() };
    Object.entries(sheet.suggested_mapping || {}).forEach(([raw, field]) => {
      if (field) next[raw] = field; else delete next[raw];
    });
    this.importMapping.set(next);
  }

  copyMappingFromActiveSheet() {
    // Already global — but force-refresh suggestions so non-active sheets that
    // share column names line up with the same field assignments.
    this.importMapping.set({ ...this.importMapping() });
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
    const preset = this.presets().find(p => p.id === id);
    if (preset) this.importMapping.set({ ...preset.mapping });
  }

  deleteActivePreset() {
    const id = this.activePresetId();
    if (!id) return;
    this.presets.set(this.presets().filter(p => p.id !== id));
    this.activePresetId.set('');
  }

  // -------------------- Totals (review step) --------------------
  totalRowsForFile(entry: FilePreviewEntry): number {
    return entry.preview?.sheets.reduce((s, sh) => s + (sh.row_count_estimate || 0), 0) || 0;
  }

  // -------------------- Import execution --------------------
  /** Quick path: skip mapping entirely and rely on backend auto-detection. */
  quickImport() {
    const files = this.files().map(e => e.file);
    if (files.length === 0) return;
    this.runImport(files, undefined);
  }

  runImportFromReview() {
    const files = this.files().map(e => e.file);
    if (files.length === 0) return;
    const mapping = Object.keys(this.importMapping()).length > 0 ? this.importMapping() : undefined;
    this.runImport(files, mapping);
  }

  private runImport(files: File[], mapping?: { [raw: string]: string }) {
    this.isImporting.set(true);
    this.importError.set(null);
    this.testCaseService.importTestCases(files, mapping, this.strategy()).subscribe({
      next: result => {
        this.importResult.set(result);
        this.isImporting.set(false);
        this.step.set('result');
        this.pushHistory(result, files);
      },
      error: err => {
        this.importError.set(this.formatError(err));
        this.isImporting.set(false);
      }
    });
  }

  private pushHistory(result: TestCaseImportResult, files: File[]) {
    const entry: ImportHistoryEntry = {
      at: new Date().toLocaleString(),
      files: files.map(f => f.name),
      totals: {
        created: result.totals.created || 0,
        updated: result.totals.updated || 0,
        skipped: result.totals.skipped || 0,
        failed: result.totals.failed || 0,
      },
      strategy: this.strategy(),
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

  /** Save the errors of a single file as a CSV download (browser-only). */
  downloadErrorsCsv(file: TestCaseImportFileResult) {
    if (!isPlatformBrowser(this.platformId)) return;
    const header = ['file', 'sheet', 'row', 'id', 'error'];
    const rows = file.errors.map(e => [
      file.file,
      e.sheet ?? '',
      e.row != null ? String(e.row) : '',
      e.id ?? '',
      (e.error ?? '').replace(/\r?\n/g, ' '),
    ]);
    const csv = [header, ...rows]
      .map(r => r.map(cell => {
        const s = String(cell ?? '');
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(','))
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
    if (err.error?.error)   return err.error.error;
    if (err.message)        return err.message;
    return 'Request failed';
  }
}
