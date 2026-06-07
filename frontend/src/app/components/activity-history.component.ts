import { Component, Input, OnChanges, SimpleChanges, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivityCommit, ActivityService } from '../services/activity.service';

/**
 * Git-style change history panel.
 *
 * Renders the activity_log feed for a single entity. Each row shows
 * the author, when, the action, and an expandable per-field diff.
 *
 * Used on both the requirement-detail and test-case-detail pages so
 * users can audit every save, see what changed, and roll back if a
 * field went sideways.
 */
@Component({
  selector: 'app-activity-history',
  standalone: true,
  imports: [CommonModule],
  template: `
    <article class="side-card history-card">
      <header class="side-card-header history-header">
        <span class="side-icon">🕘</span>
        <h4>History</h4>
        <button
          type="button"
          class="history-refresh-btn"
          (click)="reload()"
          [disabled]="loading()"
          title="Refresh history">
          ⟳
        </button>
      </header>

      <div class="side-card-body history-body">
        <div *ngIf="loading() && commits().length === 0" class="history-empty">Loading…</div>

        <div *ngIf="!loading() && commits().length === 0" class="history-empty">
          No changes recorded yet.
        </div>

        <ol class="history-list" *ngIf="commits().length > 0">
          <li *ngFor="let c of commits(); let i = index" class="history-item" [attr.data-action]="c.action">
            <div class="history-item-line">
              <span class="history-action-chip" [attr.data-action]="c.action">{{ actionLabel(c.action) }}</span>
              <span class="history-summary">{{ c.summary }}</span>
            </div>
            <div class="history-meta">
              <span class="history-author">{{ c.author_username || 'system' }}</span>
              <span class="history-sep">·</span>
              <span class="history-time" [attr.title]="c.created_at">{{ formatTime(c.created_at) }}</span>
              <span class="history-sep">·</span>
              <code class="history-hash" [title]="c.commit_hash">{{ shortHash(c.commit_hash) }}</code>
            </div>

            <div class="history-actions">
              <button
                type="button"
                class="history-toggle"
                (click)="toggleExpand(c.commit_hash)"
                *ngIf="hasDiff(c)">
                {{ expanded()[c.commit_hash] ? 'Hide diff' : 'Show diff' }}
              </button>
              <button
                type="button"
                class="history-revert"
                (click)="revert(c)"
                [disabled]="reverting()"
                *ngIf="canRevert(c, i)"
                title="Restore the entity to the state before this commit">
                Revert
              </button>
            </div>

            <div *ngIf="expanded()[c.commit_hash] && hasDiff(c)" class="history-diff">
              <div *ngFor="let kv of diffEntries(c)" class="history-diff-row">
                <div class="history-diff-field">{{ kv[0] }}</div>
                <div class="history-diff-values">
                  <div class="history-diff-old"><span class="history-diff-tag">−</span> {{ formatValue(kv[1].old) }}</div>
                  <div class="history-diff-new"><span class="history-diff-tag">+</span> {{ formatValue(kv[1].new) }}</div>
                </div>
              </div>
            </div>
          </li>
        </ol>
      </div>
    </article>
  `,
  styles: [`
    .history-card { display: flex; flex-direction: column; }
    .history-header { display: flex; align-items: center; gap: 8px; }
    .history-header h4 { flex: 1; margin: 0; }
    .history-refresh-btn {
      background: transparent; border: 1px solid var(--border-color, #e3e3e8);
      border-radius: 6px; padding: 2px 8px; cursor: pointer; font-size: 14px;
      color: var(--text-secondary, #555);
    }
    .history-refresh-btn:hover { background: var(--surface-hover, #f5f5f7); }
    .history-refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .history-body { padding: 8px 0; }
    .history-empty { color: var(--text-secondary, #888); font-size: 13px; padding: 12px 4px; text-align: center; }
    .history-list { list-style: none; padding: 0; margin: 0; }
    .history-item { padding: 10px 4px; border-bottom: 1px solid var(--border-color, #eee); }
    .history-item:last-child { border-bottom: none; }
    .history-item-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .history-summary { font-size: 13px; color: var(--text-primary, #222); }
    .history-action-chip {
      display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
      padding: 2px 6px; border-radius: 999px; text-transform: uppercase;
      background: #eef; color: #335;
    }
    .history-action-chip[data-action="create"]  { background: #e7f7ec; color: #1f7a3a; }
    .history-action-chip[data-action="update"]  { background: #eef4ff; color: #2754d8; }
    .history-action-chip[data-action="delete"]  { background: #fdecec; color: #b3261e; }
    .history-action-chip[data-action="restore"] { background: #fff4d6; color: #815400; }
    .history-meta { font-size: 11px; color: var(--text-secondary, #888); margin-top: 3px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .history-sep { opacity: 0.5; }
    .history-hash {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      background: var(--surface-muted, #f3f3f7); padding: 1px 4px; border-radius: 4px; font-size: 10.5px;
    }
    .history-actions { display: flex; gap: 8px; margin-top: 4px; }
    .history-toggle, .history-revert {
      font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid var(--border-color, #ddd);
      background: transparent; cursor: pointer;
    }
    .history-toggle:hover { background: var(--surface-hover, #f5f5f7); }
    .history-revert { color: #815400; border-color: #f0d99a; }
    .history-revert:hover:not(:disabled) { background: #fff4d6; }
    .history-revert:disabled { opacity: 0.5; cursor: not-allowed; }
    .history-diff { margin-top: 6px; padding: 6px 8px; background: var(--surface-muted, #fafafa); border-radius: 6px; }
    .history-diff-row { padding: 4px 0; border-bottom: 1px dashed #eee; }
    .history-diff-row:last-child { border-bottom: none; }
    .history-diff-field { font-size: 11px; font-weight: 600; color: var(--text-secondary, #666); margin-bottom: 2px; }
    .history-diff-values { display: flex; flex-direction: column; gap: 2px; }
    .history-diff-old, .history-diff-new {
      font-size: 11.5px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      white-space: pre-wrap; word-break: break-word;
    }
    .history-diff-old { color: #b3261e; }
    .history-diff-new { color: #1f7a3a; }
    .history-diff-tag { display: inline-block; width: 12px; text-align: center; opacity: 0.7; }
  `],
})
export class ActivityHistoryComponent implements OnChanges {
  @Input({ required: true }) entityType!: string;
  @Input({ required: true }) entityId!: string;
  /** Limit the visible commit count. Defaults to 25. */
  @Input() limit = 25;
  /** Allow the inline Revert button. Defaults to true. */
  @Input() allowRevert = true;

  private activityService = inject(ActivityService);

  commits = signal<ActivityCommit[]>([]);
  loading = signal(false);
  reverting = signal(false);
  expanded = signal<Record<string, boolean>>({});

  ngOnChanges(changes: SimpleChanges) {
    if (changes['entityType'] || changes['entityId']) {
      this.reload();
    }
  }

  reload() {
    if (!this.entityType || !this.entityId) return;
    this.loading.set(true);
    this.activityService.getForEntity(this.entityType, this.entityId, { limit: this.limit }).subscribe({
      next: data => {
        this.commits.set(data || []);
        this.loading.set(false);
      },
      error: () => {
        this.commits.set([]);
        this.loading.set(false);
      },
    });
  }

  hasDiff(c: ActivityCommit): boolean {
    return !!c.field_changes && Object.keys(c.field_changes).length > 0;
  }

  diffEntries(c: ActivityCommit): Array<[string, { old: any; new: any }]> {
    if (!c.field_changes) return [];
    return Object.entries(c.field_changes) as Array<[string, { old: any; new: any }]>;
  }

  toggleExpand(hash: string) {
    const next = { ...this.expanded() };
    next[hash] = !next[hash];
    this.expanded.set(next);
  }

  canRevert(c: ActivityCommit, idx: number): boolean {
    // The newest commit is the current state — nothing to revert to in
    // that direction. Older commits expose a Revert action that walks
    // the entity back to that commit's pre-state.
    return this.allowRevert && idx > 0 && c.action !== 'create';
  }

  revert(c: ActivityCommit) {
    if (!confirm(`Revert "${c.summary}"? A new restore entry will be added to the history.`)) return;
    this.reverting.set(true);
    this.activityService.revertToCommit(c.commit_hash).subscribe({
      next: () => {
        this.reverting.set(false);
        this.reload();
        // Notify the host page so it can reload the entity itself.
        // We use a CustomEvent so this component stays decoupled.
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sakura:activity-reverted', {
            detail: { entityType: this.entityType, entityId: this.entityId, commitHash: c.commit_hash }
          }));
        }
      },
      error: err => {
        this.reverting.set(false);
        alert(`Revert failed: ${err?.message || err}`);
      },
    });
  }

  shortHash(hash: string | undefined | null): string {
    if (!hash) return '';
    return hash.length > 7 ? hash.substring(0, 7) : hash;
  }

  actionLabel(action: string): string {
    switch (action) {
      case 'create': return 'Created';
      case 'update': return 'Updated';
      case 'delete': return 'Deleted';
      case 'restore': return 'Restored';
      default: return action;
    }
  }

  formatTime(ts: string | undefined | null): string {
    if (!ts) return '';
    try {
      const d = new Date(ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z');
      const diffMs = Date.now() - d.getTime();
      const sec = Math.round(diffMs / 1000);
      if (sec < 60) return 'just now';
      const min = Math.round(sec / 60);
      if (min < 60) return `${min}m ago`;
      const hr = Math.round(min / 60);
      if (hr < 24) return `${hr}h ago`;
      const day = Math.round(hr / 24);
      if (day < 30) return `${day}d ago`;
      return d.toLocaleDateString();
    } catch {
      return ts;
    }
  }

  formatValue(value: any): string {
    if (value === null || value === undefined) return '∅';
    if (typeof value === 'string') return value || '∅';
    if (Array.isArray(value)) return `[${value.map(v => this.formatValue(v)).join(', ')}]`;
    if (typeof value === 'object') {
      try { return JSON.stringify(value); } catch { return String(value); }
    }
    return String(value);
  }
}
