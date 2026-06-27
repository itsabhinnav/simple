import { Component, OnInit, inject, signal, OnDestroy, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { RequirementService, Requirement } from '../services/requirement.service';
import { TestCaseService, TestCase } from '../services/test-case.service';
import { Subject, Subscription } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { ActivityHistoryComponent } from './activity-history.component';

/**
 * Per-entity pending-edits cache. Edits land here BEFORE they are flushed
 * to the server. They survive page reloads, network failures, and tab
 * crashes — the old behaviour silently discarded everything the user
 * typed if the auto-save HTTP call errored. Now the edit is replayed
 * on every entity load until it succeeds (or the user explicitly
 * discards it via the toolbar).
 */
const PENDING_EDITS_KEY = (id: number) => `sakura.req.pending.${id}`;

interface PendingEdits {
  fields: Record<string, any>;
  updatedAt: number;
}

function readPending(id: number): PendingEdits | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(PENDING_EDITS_KEY(id));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.fields && typeof parsed.fields === 'object') return parsed as PendingEdits;
  } catch { /* ignored */ }
  return null;
}

function writePending(id: number, fields: Record<string, any>) {
  if (typeof localStorage === 'undefined') return;
  try {
    if (Object.keys(fields).length === 0) {
      localStorage.removeItem(PENDING_EDITS_KEY(id));
    } else {
      localStorage.setItem(PENDING_EDITS_KEY(id), JSON.stringify({ fields, updatedAt: Date.now() }));
    }
  } catch { /* quota / private mode */ }
}

@Component({
  selector: 'app-requirement-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, ActivityHistoryComponent],
  templateUrl: './requirement-detail.component.html',
  styleUrl: './requirement-detail.component.scss'
})
export class RequirementDetailComponent implements OnInit, OnDestroy {
  private requirementService = inject(RequirementService);
  private testCaseService = inject(TestCaseService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  requirement = signal<Requirement | null>(null);
  linkedTestCases = signal<TestCase[]>([]);
  isLoading = signal(false);
  isLoadingTestCases = signal(false);
  error = signal<string | null>(null);
  requirementId = signal<number | null>(null);
  isSaving = signal(false);
  saveStatus = signal<'idle' | 'saving' | 'saved' | 'error'>('idle');
  editingField = signal<string | null>(null);

  // Pending edits that have not yet been confirmed by the server. Keyed by
  // logical field name (e.g. "title"). Buffered so a failed network call
  // does NOT cause the visible value to revert.
  pendingFields = signal<Record<string, any>>({});
  // Map<field, retryCount> so we can stop hammering on permanent failures.
  private retryCounts: Record<string, number> = {};
  // How many times we'll try a single field automatically before giving up.
  private readonly MAX_RETRIES = 5;

  private saveSubject = new Subject<{ field: string; value: any }>();
  private saveSubscription?: Subscription;

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.requirementId.set(+id);
      this.loadRequirement(+id);
    }

    this.saveSubscription = this.saveSubject.pipe(
      debounceTime(800)
    ).subscribe(({ field, value }) => {
      this.saveField(field, value);
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
    if (detail.entityType === 'requirement' && this.requirementId() != null) {
      this.loadRequirement(this.requirementId()!);
    }
  };

  /**
   * Warn before navigating away if there are pending un-saved edits.
   * The values are persisted to localStorage too, but this gives the user
   * a chance to explicitly retry before leaving.
   */
  @HostListener('window:beforeunload', ['$event'])
  onBeforeUnload(e: BeforeUnloadEvent) {
    if (Object.keys(this.pendingFields()).length > 0) {
      e.preventDefault();
      e.returnValue = '';
    }
  }

  loadRequirement(id: number) {
    this.isLoading.set(true);
    this.error.set(null);

    this.requirementService.getRequirementById(id).subscribe({
      next: (requirement) => {
        if (requirement) {
          // Layer any pending (un-flushed) edits on top of the server
          // state so the user keeps seeing what they typed even after a
          // reload or network blip.
          const pending = readPending(id);
          if (pending && pending.fields && Object.keys(pending.fields).length > 0) {
            this.pendingFields.set({ ...pending.fields });
            this.requirement.set({ ...requirement, ...pending.fields });
            // Re-queue every pending field for another save attempt.
            for (const [f, v] of Object.entries(pending.fields)) {
              this.saveSubject.next({ field: f, value: v });
            }
          } else {
            this.pendingFields.set({});
            this.requirement.set(requirement);
          }
          this.loadLinkedTestCases(requirement.requirement_id, requirement.linked_test_case_ids);
        } else {
          this.error.set('Requirement not found');
        }
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load requirement');
        this.isLoading.set(false);
        console.error('Error loading requirement:', err);
      }
    });
  }

  loadLinkedTestCases(requirementId: string, linkedTestCaseIds?: string) {
    this.isLoadingTestCases.set(true);
    const fromReqField = (linkedTestCaseIds || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    this.testCaseService.getTestCases().subscribe({
      next: (testCases) => {
        const linked = testCases.filter((tc) =>
          TestCaseService.mvArray(tc.associated_requirement_id).includes(requirementId) ||
          fromReqField.includes(tc.test_case_id)
        );
        this.linkedTestCases.set(linked);
        this.isLoadingTestCases.set(false);
      },
      error: () => {
        this.linkedTestCases.set([]);
        this.isLoadingTestCases.set(false);
      }
    });
  }

  navigateToTestCase(testCaseId: string) {
    this.router.navigate(['/test-cases', testCaseId]);
  }

  getPriorityClass(priority: string): string {
    const priorityMap: { [key: string]: string } = {
      'P4': 'priority-low',
      'P3': 'priority-medium',
      'P2': 'priority-high',
      'P1': 'priority-critical'
    };
    return priorityMap[priority] || 'priority-default';
  }

  goBack() {
    if (typeof window !== 'undefined') {
      window.history.back();
    }
  }

  deleteRequirement() {
    if (!this.requirementId() || !confirm('Are you sure you want to delete this requirement?')) {
      return;
    }

    this.requirementService.deleteRequirement(this.requirementId()!).subscribe({
      next: () => {
        // Clean up any pending un-saved edits for this entity.
        writePending(this.requirementId()!, {});
        if (typeof window !== 'undefined') {
          window.history.back();
        }
      },
      error: (err) => {
        this.error.set('Failed to delete requirement');
        console.error('Error deleting requirement:', err);
      }
    });
  }

  startEdit(field: string) {
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
    if (!this.requirement()) return;

    const current = this.requirement()!;
    this.requirement.set({ ...current, [field]: value });

    // Buffer the edit in the pending map + persist to localStorage so a
    // reload/network blip can't lose it.
    const nextPending = { ...this.pendingFields(), [field]: value };
    this.pendingFields.set(nextPending);
    if (this.requirementId() != null) {
      writePending(this.requirementId()!, nextPending);
    }
    this.retryCounts[field] = 0;

    this.saveSubject.next({ field, value });
    this.saveStatus.set('saving');
  }

  /**
   * Manual retry button: replays every pending field through the
   * autosave pipeline. Reachable via the error pill when a save fails.
   */
  retryPending() {
    const pending = this.pendingFields();
    for (const [field, value] of Object.entries(pending)) {
      this.retryCounts[field] = 0;
      this.saveSubject.next({ field, value });
    }
  }

  /** Discard local pending edits and re-sync with the server state. */
  discardPending() {
    if (Object.keys(this.pendingFields()).length === 0) return;
    if (!confirm('Discard unsaved edits and reload from server?')) return;
    this.pendingFields.set({});
    this.retryCounts = {};
    if (this.requirementId() != null) {
      writePending(this.requirementId()!, {});
      this.loadRequirement(this.requirementId()!);
    }
    this.saveStatus.set('idle');
  }

  pendingFieldNames(): string[] {
    return Object.keys(this.pendingFields());
  }

  hasPendingEdits(): boolean {
    return this.pendingFieldNames().length > 0;
  }

  private saveField(field: string, value: any) {
    if (!this.requirementId() || !this.requirement()) return;

    this.isSaving.set(true);
    this.saveStatus.set('saving');

    const updateData: any = {};

    // Translate the frontend's physical column-style names to the
    // logical field names the backend update schema understands. The
    // backend additionally accepts the legacy aliases for resilience,
    // but the canonical wire format is `when` / `then`.
    if (field === 'when_action') {
      updateData.when = value;
    } else if (field === 'then_result') {
      updateData.then = value;
    } else {
      updateData[field] = value;
    }

    this.requirementService.updateRequirement(this.requirementId()!, updateData).subscribe({
      next: (updatedRequirement) => {
        if (updatedRequirement) {
          // Merge server values back onto the local copy. We KEEP any
          // pending edits that arrived during the request (so the user's
          // newer keystrokes aren't overwritten by a now-stale response).
          const stillPending = { ...this.pendingFields() };
          delete stillPending[field];
          // If the value typed during the request is the same as what
          // we just sent, treat that field as flushed too.
          const merged: Requirement = { ...this.requirement()!, ...updatedRequirement };
          for (const f of Object.keys(stillPending)) {
            (merged as any)[f] = stillPending[f];
          }
          this.requirement.set(merged);
          this.pendingFields.set(stillPending);
          if (this.requirementId() != null) {
            writePending(this.requirementId()!, stillPending);
          }
          this.retryCounts[field] = 0;

          if (Object.keys(stillPending).length === 0) {
            this.saveStatus.set('saved');
            setTimeout(() => {
              if (this.saveStatus() === 'saved') this.saveStatus.set('idle');
            }, 2000);
          } else {
            this.saveStatus.set('saving');
          }
        }
        this.isSaving.set(false);
      },
      error: (err) => {
        console.error('Error saving field:', err);
        // CRITICAL: do NOT reload the requirement here. Reloading would
        // overwrite the value the user just typed, which was the entire
        // "edits disappear on retry" symptom. Keep the value local and
        // let the user see + retry.
        this.saveStatus.set('error');
        this.error.set(`Failed to save ${field}: ${err?.message || err}`);
        this.isSaving.set(false);

        const attempt = (this.retryCounts[field] || 0) + 1;
        this.retryCounts[field] = attempt;
        if (attempt < this.MAX_RETRIES) {
          // Exponential backoff: 1s, 2s, 4s, 8s, 16s.
          const delayMs = Math.pow(2, attempt - 1) * 1000;
          setTimeout(() => {
            // Read the latest pending value so the user's more-recent
            // typing wins over the stale value that just failed.
            const latest = this.pendingFields()[field];
            if (latest === undefined) return;
            this.saveSubject.next({ field, value: latest });
          }, delayMs);
        } else {
          // Hand-off to the user: error pill stays visible with retry button.
          setTimeout(() => {
            // Clear inline error text after a while so the page isn't yelling,
            // but keep the pending edits + retry button accessible.
            if (this.saveStatus() === 'error') {
              this.error.set(null);
            }
          }, 6000);
        }
      }
    });
  }
}
