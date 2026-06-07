import { Injectable, signal } from '@angular/core';

/**
 * Coordinates an application reload after settings changes that require
 * the SPA to re-bootstrap (e.g. database schema migrations, feature flag
 * toggles, LLM provider swaps).
 *
 * Why a full reload? Most data services in the app cache responses in
 * memory or in `localStorage`. After a schema change those caches are
 * stale (columns may have appeared, disappeared, or been renamed) and a
 * targeted invalidation would have to know every consumer. A full
 * `window.location.reload()` is the only universal answer.
 *
 * Cross-tab coordination: when one admin tab reloads after a setting
 * change, other open tabs of the app must reload too — otherwise they
 * keep operating against the old schema. We use the standard
 * `BroadcastChannel` API where available (every modern Chromium /
 * Firefox / Safari build) with a `localStorage` event fallback.
 */
@Injectable({ providedIn: 'root' })
export class SettingsReloadService {
  private readonly CHANNEL_NAME = 'sakura-settings-reload';
  private readonly STORAGE_KEY = '__sakura_settings_reload__';
  private channel: BroadcastChannel | null = null;
  /** Reactive flag — set when a reload has been scheduled. UI may show a banner. */
  readonly pendingReload = signal(false);
  /** Optional reason string surfaced to the user. */
  readonly pendingReason = signal<string | null>(null);

  constructor() {
    if (typeof window === 'undefined') return;
    try {
      if ('BroadcastChannel' in window) {
        this.channel = new BroadcastChannel(this.CHANNEL_NAME);
        this.channel.onmessage = (ev) => this.onRemoteReload(ev.data?.reason);
      }
    } catch {
      this.channel = null;
    }
    window.addEventListener('storage', (ev) => {
      if (ev.key === this.STORAGE_KEY && ev.newValue) {
        try {
          const payload = JSON.parse(ev.newValue);
          this.onRemoteReload(payload?.reason);
        } catch {
          this.onRemoteReload(null);
        }
      }
    });
  }

  /**
   * Schedule a full reload of the current tab and broadcast the same
   * intent to every other open tab.
   *
   * @param reason  Human-readable summary used by the toast/banner.
   * @param delayMs Milliseconds to wait before actually reloading.
   *                Default 1200ms so a success toast has time to flash.
   */
  scheduleReload(reason: string, delayMs = 1200): void {
    this.pendingReload.set(true);
    this.pendingReason.set(reason);
    this.broadcast(reason);
    if (typeof window === 'undefined') return;
    setTimeout(() => {
      try {
        window.location.reload();
      } catch {
        // ignore — best effort
      }
    }, Math.max(0, delayMs));
  }

  /**
   * Immediately reload the current tab without rescheduling, useful for
   * the explicit "Restart app" button.
   */
  reloadNow(reason = 'Manual restart'): void {
    this.broadcast(reason);
    if (typeof window === 'undefined') return;
    window.location.reload();
  }

  private broadcast(reason: string): void {
    const payload = { reason, at: Date.now() };
    try {
      this.channel?.postMessage(payload);
    } catch {
      /* ignore */
    }
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(this.STORAGE_KEY, JSON.stringify(payload));
        window.localStorage.removeItem(this.STORAGE_KEY);
      }
    } catch {
      /* ignore */
    }
  }

  private onRemoteReload(reason: string | null): void {
    if (this.pendingReload()) return; // already scheduled locally
    this.pendingReload.set(true);
    this.pendingReason.set(reason || 'Settings changed in another tab');
    setTimeout(() => {
      try {
        window.location.reload();
      } catch {
        /* ignore */
      }
    }, 600);
  }
}
