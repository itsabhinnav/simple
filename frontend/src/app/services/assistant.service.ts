import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { API_URL, API_BASE } from '../app-settings';

export type AssistantKind = 'requirements' | 'test_cases' | 'design_tickets' | 'specs';

export interface AssistantCitation {
  kind: 'requirement' | 'test_case' | 'design_ticket' | 'spec';
  id: string;
  title: string;
  route: string;
  score: number;
}

export interface AssistantChatResponse {
  answer: string;
  provider: string;
  retrieval_mode?: 'hybrid' | 'vector' | 'lexical';
  citations: AssistantCitation[];
  matched_terms: string[];
  context_counts: Record<string, number>;
}

export interface AssistantIndexStatus {
  enabled: boolean;
  backend: 'sqlite-vec' | 'memory' | 'disabled' | string;
  provider: string | null;
  embedding_model: string | null;
  dimension: number | null;
  total_vectors: number;
  per_kind_counts: Record<string, number>;
  last_indexed_at: number | null;
  last_indexed_version: number | null;
  last_error: string | null;
  in_progress: boolean;
}

export interface AssistantIndexRefreshResponse {
  summary: Record<string, any>;
  status: AssistantIndexStatus;
}

export interface AssistantChatRequest {
  question: string;
  history?: { role: 'user' | 'assistant'; content: string }[];
  kinds?: AssistantKind[];
  provider?: string;
}

export interface AssistantProvidersResponse {
  providers: string[];
  default: string | null;
}

interface Envelope<T> { success: boolean; data?: T; message?: string; error?: string; }

export interface AssistantStreamHandlers {
  onMeta: (meta: Omit<AssistantChatResponse, 'answer'>) => void;
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

@Injectable({ providedIn: 'root' })
export class AssistantService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_URL}/assistant`;

  chat(req: AssistantChatRequest): Observable<AssistantChatResponse> {
    return this.http.post<Envelope<AssistantChatResponse>>(`${this.baseUrl}/chat`, req).pipe(
      map(r => {
        if (!r.success || !r.data) throw new Error(r.message || r.error || 'Chat failed');
        return r.data;
      }),
      catchError(err => throwError(() => new Error(err?.error?.message || err?.message || 'Chat failed')))
    );
  }

  listProviders(): Observable<AssistantProvidersResponse> {
    return this.http.get<Envelope<AssistantProvidersResponse>>(`${this.baseUrl}/providers`).pipe(
      map(r => r.data ?? { providers: [], default: null }),
      catchError(() => throwError(() => new Error('Failed to load providers')))
    );
  }

  indexStatus(): Observable<AssistantIndexStatus> {
    return this.http.get<Envelope<AssistantIndexStatus>>(`${this.baseUrl}/index/status`).pipe(
      map(r => r.data as AssistantIndexStatus),
      catchError(err => throwError(() => new Error(err?.error?.message || 'Failed to load index status')))
    );
  }

  refreshIndex(force = false): Observable<AssistantIndexRefreshResponse> {
    return this.http.post<Envelope<AssistantIndexRefreshResponse>>(`${this.baseUrl}/index/refresh`, { force }).pipe(
      map(r => {
        if (!r.success || !r.data) throw new Error(r.message || 'Refresh failed');
        return r.data;
      }),
      catchError(err => throwError(() => new Error(err?.error?.message || 'Refresh failed')))
    );
  }

  /**
   * Stream the assistant reply via SSE. Uses fetch + ReadableStream rather
   * than EventSource so we can POST a JSON body (EventSource is GET-only).
   * Returns a function that aborts the in-flight request when called.
   */
  stream(req: AssistantChatRequest, handlers: AssistantStreamHandlers): () => void {
    const controller = new AbortController();
    const url = `${API_BASE}/api/assistant/stream`;

    (async () => {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
          body: JSON.stringify(req),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          handlers.onError(`HTTP ${response.status}`);
          return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const evt of events) {
            this.dispatchEvent(evt, handlers);
          }
        }
        if (buffer.trim()) this.dispatchEvent(buffer, handlers);
        handlers.onDone();
      } catch (err: any) {
        if (err?.name === 'AbortError') return;
        handlers.onError(err?.message || 'Stream failed');
      }
    })();

    return () => controller.abort();
  }

  private dispatchEvent(raw: string, handlers: AssistantStreamHandlers): void {
    const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
    let event = 'message';
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length === 0) return;
    let payload: any;
    try { payload = JSON.parse(dataLines.join('\n')); } catch { return; }
    if (event === 'meta') handlers.onMeta(payload);
    else if (event === 'token') handlers.onToken(payload.text || '');
    else if (event === 'done') { /* handled by stream end */ }
    else if (event === 'error') handlers.onError(payload.message || 'stream error');
  }
}
