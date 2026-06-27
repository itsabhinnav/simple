import { Component, OnInit, inject, signal, OnDestroy, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { TestCaseService, TestCase, TestCaseDropdowns, TEST_CASE_MULTI_VALUE_FIELDS } from '../services/test-case.service';
import { RequirementService } from '../services/requirement.service';
import { Subject, Subscription } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { ActivityHistoryComponent } from './activity-history.component';

// Pending un-flushed edits keyed by test_case_id. Survives reloads and
// network blips so the user never loses what they typed.
const TC_PENDING_KEY = (id: string) => `sakura.tc.pending.${id}`;

interface TcPendingEdits { fields: Record<string, any>; updatedAt: number; }

function readTcPending(id: string): TcPendingEdits | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(TC_PENDING_KEY(id));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.fields && typeof parsed.fields === 'object') return parsed as TcPendingEdits;
  } catch { /* ignored */ }
  return null;
}

function writeTcPending(id: string, fields: Record<string, any>) {
  if (typeof localStorage === 'undefined') return;
  try {
    if (Object.keys(fields).length === 0) localStorage.removeItem(TC_PENDING_KEY(id));
    else localStorage.setItem(TC_PENDING_KEY(id), JSON.stringify({ fields, updatedAt: Date.now() }));
  } catch { /* quota / private mode */ }
}

@Component({
  selector: 'app-test-case-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, ActivityHistoryComponent],
  templateUrl: './test-case-detail.component.html',
  styleUrl: './test-case-detail.component.scss'
})
export class TestCaseDetailComponent implements OnInit, OnDestroy {
  private testCaseService = inject(TestCaseService);
  private requirementService = inject(RequirementService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  testCase = signal<TestCase | null>(null);
  isLoading = signal(false);
  error = signal<string | null>(null);
  testCaseId = signal<string | null>(null);
  isSaving = signal(false);
  saveStatus = signal<'idle' | 'saving' | 'saved' | 'error'>('idle');
  editingField = signal<string | null>(null);
  pendingFields = signal<Record<string, any>>({});
  private retryCounts: Record<string, number> = {};
  private readonly MAX_RETRIES = 5;
  /**
   * Read-only by default. Users must press the explicit Edit button before any
   * field can be modified. Inline edit affordances (pencil glyph, hover, chip
   * clicks, hero <select> dropdowns) all gate on this signal.
   */
  editMode = signal(false);
  automationEnabled = signal(false);
  isExecuting = signal(false);
  executionNotice = signal<string | null>(null);
  /** Dropdown options sourced from `config.yaml > test_case_dropdowns`. */
  dropdowns = signal<TestCaseDropdowns | null>(null);

  /** Adapter so the template can render a multi-value field as `chip`s. */
  mvArray(value: any): string[] {
    return TestCaseService.mvArray(value);
  }

  /** Join multi-value fields for text-input display. */
  mvDisplay(value: any): string {
    return TestCaseService.mvDisplay(value);
  }

  private isMultiValueField(field: string): boolean {
    return (TEST_CASE_MULTI_VALUE_FIELDS as readonly string[]).includes(field);
  }

  private normalizeFieldValue(field: string, value: any): any {
    if (this.isMultiValueField(field)) {
      return TestCaseService.mvArray(value);
    }
    return value;
  }

  /** Toggle a value inside a multi-value field and persist the change. */
  toggleMulti(field: string, value: string) {
    if (!this.editMode()) return;
    const current = TestCaseService.mvArray((this.testCase() as any)?.[field]);
    const next = current.includes(value)
      ? current.filter(v => v !== value)
      : [...current, value];
    this.onFieldChange(field, next);
  }

  /**
   * Flip between read-only and edit mode. Closing edit mode also closes any
   * currently-open inline editor so the page settles into a clean view state.
   */
  toggleEditMode() {
    const next = !this.editMode();
    if (!next) {
      this.flushPendingSaves();
      this.stopEdit();
    }
    this.editMode.set(next);
  }

  /** Bypass debounce — call when leaving edit mode or before navigation. */
  private flushPendingSaves() {
    const pending = { ...this.pendingFields() };
    for (const [field, value] of Object.entries(pending)) {
      this.saveField(field, value);
    }
  }

  isMultiSelected(field: string, value: string): boolean {
    return TestCaseService.mvArray((this.testCase() as any)?.[field]).includes(value);
  }

  /** Dropdown options plus the current DB value when it isn't in config. */
  dropdownOptions(field: 'priority' | 'test_type' | 'regulation', current?: string): string[] {
    const configured = [...(this.dropdowns()?.[field] || [])];
    const cur = (current ?? '').trim();
    if (cur && !configured.includes(cur)) {
      return [cur, ...configured];
    }
    return configured;
  }
  
  private saveSubject = new Subject<{ field: string; value: any }>();
  private saveSubscription?: Subscription;

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      // Backend expects test_case_id (string), not numeric id
      this.testCaseId.set(id);
      this.loadTestCase(id);
    }

    // Allow upstream pages (e.g. the Test Case list pencil button) to deep-link
    // straight into edit mode by appending `?edit=1`. Anything truthy flips the
    // toggle on; absent / "0" leaves the page in default read-only mode.
    const editFlag = this.route.snapshot.queryParamMap.get('edit');
    if (editFlag && editFlag !== '0' && editFlag.toLowerCase() !== 'false') {
      this.editMode.set(true);
    }

    // Set up auto-save with debouncing
    this.saveSubscription = this.saveSubject.pipe(
      debounceTime(800)
    ).subscribe(({ field, value }) => {
      this.saveField(field, value);
    });

    // Load configurable dropdown options (cached in the service).
    this.testCaseService.getDropdowns().subscribe({
      next: data => this.dropdowns.set(data),
      error: err => console.error('Failed to load dropdowns', err),
    });
    this.testCaseService.getAutomationStatus().subscribe({
      next: status => this.automationEnabled.set(!!status.enabled),
      error: () => this.automationEnabled.set(false),
    });

    if (typeof window !== 'undefined') {
      window.addEventListener('sakura:activity-reverted', this.onReverted as EventListener);
    }
  }

  ngOnDestroy() {
    this.saveSubscription?.unsubscribe();
    if (typeof window !== 'undefined') {
      window.removeEventListener('sakura:activity-reverted', this.onReverted as EventListener);
    }
  }

  private onReverted = (evt: Event) => {
    const detail = (evt as CustomEvent).detail || {};
    if (detail.entityType === 'test_case' && this.testCaseId()) {
      this.loadTestCase(this.testCaseId()!);
    }
  };

  @HostListener('window:beforeunload', ['$event'])
  onBeforeUnload(e: BeforeUnloadEvent) {
    if (Object.keys(this.pendingFields()).length > 0) {
      this.flushPendingSaves();
      e.preventDefault();
      e.returnValue = '';
    }
  }

  hasPendingEdits(): boolean { return Object.keys(this.pendingFields()).length > 0; }
  pendingFieldNames(): string[] { return Object.keys(this.pendingFields()); }

  retryPending() {
    const pending = this.pendingFields();
    for (const [field, value] of Object.entries(pending)) {
      this.retryCounts[field] = 0;
      this.saveSubject.next({ field, value });
    }
  }

  discardPending() {
    if (!this.hasPendingEdits()) return;
    if (!confirm('Discard unsaved edits and reload from server?')) return;
    this.pendingFields.set({});
    this.retryCounts = {};
    if (this.testCaseId()) {
      writeTcPending(this.testCaseId()!, {});
      this.loadTestCase(this.testCaseId()!);
    }
    this.saveStatus.set('idle');
  }

  loadTestCase(id: string) {
    this.isLoading.set(true);
    this.error.set(null);

    this.testCaseService.getTestCaseById(id).subscribe({
      next: (testCase) => {
        if (testCase) {
          // Layer pending un-flushed edits on top of the server state so
          // a reload (or a save retry triggered by a network blip) never
          // wipes what the user typed.
          const pending = readTcPending(id);
          if (pending && pending.fields && Object.keys(pending.fields).length > 0) {
            this.pendingFields.set({ ...pending.fields });
            this.testCase.set({ ...testCase, ...pending.fields });
            for (const [f, v] of Object.entries(pending.fields)) {
              this.saveSubject.next({ field: f, value: v });
            }
          } else {
            this.pendingFields.set({});
            this.testCase.set(testCase);
          }
        } else {
          this.error.set('Test case not found');
        }
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load test case');
        this.isLoading.set(false);
        console.error('Error loading test case:', err);
      }
    });
  }

  getStatusClass(status: string): string {
    const statusMap: { [key: string]: string } = {
      'Pass': 'status-pass',
      'Fail': 'status-fail',
      'Blocked': 'status-blocked',
      'Not Run': 'status-not-run',
      'In Progress': 'status-progress'
    };
    return statusMap[status] || 'status-default';
  }

  getPriorityClass(priority: string): string {
    const priorityMap: { [key: string]: string } = {
      'P3': 'priority-low',
      'P2': 'priority-medium',
      'P1': 'priority-high',
    };
    return priorityMap[priority] || 'priority-default';
  }

  getTypeClass(testType: string): string {
    const typeMap: { [key: string]: string } = {
      'Positive': 'status-pass',
      'Negative': 'status-fail',
      'Boundary': 'status-blocked',
      'Performance': 'status-progress'
    };
    return typeMap[testType] || 'status-default';
  }

  goBack() {
    if (typeof window !== 'undefined') {
      window.history.back();
    }
  }

  executeTestCase() {
    const id = this.testCaseId();
    if (!id) return;
    if (!this.automationEnabled()) {
      this.executionNotice.set('Test automation is disabled in server config.');
      return;
    }
    this.isExecuting.set(true);
    this.executionNotice.set(null);
    this.testCaseService.executeTestCase(id).subscribe({
      next: (result) => {
        this.executionNotice.set(result.message || 'Execution finished');
        this.isExecuting.set(false);
      },
      error: (err) => {
        this.executionNotice.set(err?.message || 'Execution failed');
        this.isExecuting.set(false);
      },
    });
  }

  deleteTestCase() {
    if (!this.testCaseId() || !confirm('Are you sure you want to delete this test case?')) {
      return;
    }

    this.testCaseService.deleteTestCase(String(this.testCaseId()!)).subscribe({
      next: () => {
        writeTcPending(this.testCaseId()!, {});
        if (typeof window !== 'undefined') {
          window.history.back();
        }
      },
      error: (err) => {
        this.error.set('Failed to delete test case');
        console.error('Error deleting test case:', err);
      }
    });
  }

  navigateToRequirement(requirementId: string) {
    if (!requirementId) {
      console.error('Cannot navigate: requirement ID is empty');
      return;
    }

    // Get the requirement by requirement_id to find its numeric id
    this.requirementService.getRequirementByRequirementId(requirementId).subscribe({
      next: (requirement) => {
        if (requirement && requirement.id) {
          console.log('Navigating to requirement detail:', requirement.id);
          this.router.navigate(['/requirements', requirement.id]);
        } else {
          console.error('Requirement not found:', requirementId);
          alert(`Requirement ${requirementId} not found`);
        }
      },
      error: (err) => {
        console.error('Error loading requirement:', err);
        alert(`Failed to load requirement ${requirementId}`);
      }
    });
  }

  startEdit(field: string) {
    // Inline editing is gated by the explicit Edit toggle; in read-only mode
    // every click on a field is a no-op.
    if (!this.editMode()) return;
    this.editingField.set(field);
    setTimeout(() => {
      if (typeof document === 'undefined') return;
      const el = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(
        `[data-edit-field="${field}"]`
      );
      if (!el) return;
      el.focus();
      if (el.tagName === 'TEXTAREA') {
        const len = el.value.length;
        el.setSelectionRange(len, len);
      } else if ('select' in el && typeof (el as HTMLInputElement).select === 'function') {
        (el as HTMLInputElement).select();
      }
    }, 0);
  }

  stopEdit() {
    this.editingField.set(null);
  }

  isEditing(field: string): boolean {
    return this.editingField() === field;
  }

  onEditKeydown(event: KeyboardEvent, isMultiline: boolean = false) {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.stopEdit();
    } else if (event.key === 'Enter' && !isMultiline && !event.shiftKey) {
      event.preventDefault();
      this.stopEdit();
    }
  }

  onFieldChange(field: string, value: any) {
    if (!this.testCase()) return;
    if (!this.editMode()) return;

    const normalized = this.normalizeFieldValue(field, value);
    const current = this.testCase()!;
    this.testCase.set({ ...current, [field]: normalized });

    const nextPending = { ...this.pendingFields(), [field]: normalized };
    this.pendingFields.set(nextPending);
    if (this.testCaseId()) writeTcPending(this.testCaseId()!, nextPending);
    this.retryCounts[field] = 0;

    this.saveSubject.next({ field, value: normalized });
    this.saveStatus.set('saving');
  }

  private valuesMatch(field: string, a: any, b: any): boolean {
    if (this.isMultiValueField(field)) {
      const aa = TestCaseService.mvArray(a);
      const bb = TestCaseService.mvArray(b);
      return aa.length === bb.length && aa.every((v, i) => v === bb[i]);
    }
    return (a ?? '') === (b ?? '');
  }

  private handleSaveFailure(field: string, err: any) {
    console.error('Error saving field:', err);
    this.saveStatus.set('error');
    this.error.set(`Failed to save ${field}: ${err?.message || err}`);
    this.isSaving.set(false);

    const attempt = (this.retryCounts[field] || 0) + 1;
    this.retryCounts[field] = attempt;
    if (attempt < this.MAX_RETRIES) {
      const delayMs = Math.pow(2, attempt - 1) * 1000;
      setTimeout(() => {
        const latest = this.pendingFields()[field];
        if (latest === undefined) return;
        this.saveSubject.next({ field, value: latest });
      }, delayMs);
    } else {
      setTimeout(() => {
        if (this.saveStatus() === 'error') this.error.set(null);
      }, 6000);
    }
  }

  private saveField(field: string, value: any) {
    if (!this.testCaseId() || !this.testCase()) return;

    const normalized = this.normalizeFieldValue(field, value);
    this.isSaving.set(true);
    this.saveStatus.set('saving');

    const updateData: Record<string, any> = { [field]: normalized };

    this.testCaseService.updateTestCase(this.testCaseId()!, updateData).subscribe({
      next: (updatedTestCase) => {
        const serverValue = (updatedTestCase as any)?.[field];
        if (!this.valuesMatch(field, normalized, serverValue)) {
          // Server echo doesn't match what we sent — keep local + pending.
          console.warn(`Save echo mismatch for ${field}; keeping local value`);
          this.handleSaveFailure(field, new Error('Server returned unexpected value'));
          return;
        }

        const stillPending = { ...this.pendingFields() };
        delete stillPending[field];
        const merged: TestCase = { ...this.testCase()!, ...updatedTestCase };
        for (const f of Object.keys(stillPending)) {
          (merged as any)[f] = stillPending[f];
        }
        this.testCase.set(merged);
        this.pendingFields.set(stillPending);
        if (this.testCaseId()) writeTcPending(this.testCaseId()!, stillPending);
        this.retryCounts[field] = 0;

        if (Object.keys(stillPending).length === 0) {
          this.saveStatus.set('saved');
          setTimeout(() => {
            if (this.saveStatus() === 'saved') this.saveStatus.set('idle');
          }, 2000);
        } else {
          this.saveStatus.set('saving');
        }
        this.isSaving.set(false);
      },
      error: (err) => this.handleSaveFailure(field, err),
    });
  }
}

