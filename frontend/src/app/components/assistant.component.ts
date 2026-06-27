import {
  Component,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import {
  AssistantCitation,
  AssistantIndexStatus,
  AssistantKind,
  AssistantService,
} from '../services/assistant.service';
import {
  Conversation,
  ConversationStore,
  StoredChatMessage,
} from '../services/conversation-store.service';
import { TranslationService } from '../services/translation.service';

interface ChatMessage extends StoredChatMessage {
  streaming?: boolean;
  copied?: boolean;
  citationsExpanded?: boolean;
}

const ALL_KINDS: AssistantKind[] = ['requirements', 'test_cases', 'specs'];

const SUGGESTED_PROMPTS = [
  'Is there any requirement and test cases for BT disconnection?',
  'Which P1 requirements are still in Draft?',
  'List negative test cases for the login feature.',
  'Summarize the latest specification changes.',
];

@Component({
  selector: 'app-assistant',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './assistant.component.html',
  styleUrl: './assistant.component.scss',
})
export class AssistantComponent implements OnInit, OnDestroy {
  private assistant = inject(AssistantService);
  private store = inject(ConversationStore);
  private router = inject(Router);
  private i18n = inject(TranslationService);

  @ViewChild('scrollEnd') private scrollEnd?: ElementRef<HTMLDivElement>;
  @ViewChild('composerInput') private composerInput?: ElementRef<HTMLTextAreaElement>;

  // ---- Chat state ---------------------------------------------------------
  messages = signal<ChatMessage[]>([]);
  input = signal('');
  isStreaming = signal(false);
  error = signal<string | null>(null);

  // ---- Conversation state -------------------------------------------------
  activeConversationId = signal<string | null>(null);
  conversations = this.store.ordered;
  historyOpen = signal(true);
  renamingId = signal<string | null>(null);
  renameDraft = signal('');

  // ---- Providers / filters ------------------------------------------------
  providers = signal<string[]>([]);
  selectedProvider = signal<string>('');
  defaultProvider = signal<string | null>(null);

  kindFilters = signal<Record<AssistantKind, boolean>>({
    requirements: true,
    test_cases: true,
    design_tickets: false,
    specs: true,
  });

  // ---- RAG index status ---------------------------------------------------
  indexStatus = signal<AssistantIndexStatus | null>(null);
  reindexing = signal(false);
  reindexMsg = signal<string | null>(null);

  // ---- Derived ------------------------------------------------------------
  readonly suggested = SUGGESTED_PROMPTS;
  readonly allKinds = ALL_KINDS;
  readonly kindLabel: Record<AssistantKind, string> = {
    requirements: 'Requirements',
    test_cases: 'Test Cases',
    design_tickets: 'Design Tickets',
    specs: 'Specifications',
  };
  readonly kindIcon: Record<AssistantKind, string> = {
    requirements: '📋',
    test_cases: '🧪',
    design_tickets: '🎨',
    specs: '📑',
  };

  readonly visibleKinds = ALL_KINDS;

  readonly citationLimit = 6;

  hasMessages = computed(() => this.messages().length > 0);

  toggleCitations(m: ChatMessage): void {
    this.patchAssistant(m.id, x => ({ ...x, citationsExpanded: !x.citationsExpanded }));
  }
  selectedKinds = computed<AssistantKind[]>(() =>
    (Object.entries(this.kindFilters()) as [AssistantKind, boolean][])
      .filter(([, v]) => v).map(([k]) => k)
  );

  indexFreshnessLabel = computed(() => {
    this.i18n.currentLang();
    const st = this.indexStatus();
    if (!st) return this.i18n.translateLiteral('index: loading…');
    if (!st.enabled) return this.i18n.translateLiteral('index: disabled');
    if (st.in_progress) return this.i18n.translateLiteral('index: reindexing…');
    if (!st.last_indexed_at) {
      return this.i18n.translateLiteral(`${st.backend} · not yet built`);
    }
    const seconds = Math.round(Date.now() / 1000 - st.last_indexed_at);
    const age = seconds < 60 ? `${seconds}s` : seconds < 3600 ? `${Math.round(seconds / 60)}m` : `${Math.round(seconds / 3600)}h`;
    return this.i18n.translateLiteral(`${st.backend} · ${st.total_vectors} vectors · synced ${age} ago`);
  });

  // ---- Internals ----------------------------------------------------------
  private cancelStream: (() => void) | null = null;
  private msgSeq = 0;
  private statusTimer?: number;
  private saveTimer?: number;

  constructor() {
    // Smooth scroll to end whenever messages change
    effect(() => {
      this.messages();
      queueMicrotask(() => this.scrollEnd?.nativeElement?.scrollIntoView({ behavior: 'smooth' }));
    });

    // Auto-persist current conversation (debounced)
    effect(() => {
      const msgs = this.messages();
      if (msgs.length === 0) return;
      if (this.saveTimer) window.clearTimeout(this.saveTimer);
      this.saveTimer = window.setTimeout(() => this.persistCurrent(), 400);
    });
  }

  ngOnInit(): void {
    this.assistant.listProviders().subscribe({
      next: r => {
        this.providers.set(r.providers || []);
        this.defaultProvider.set(r.default);
        if (!this.selectedProvider() && r.default) this.selectedProvider.set(r.default);
      },
      error: () => {},
    });
    this.refreshIndexStatus();
    this.statusTimer = window.setInterval(() => this.refreshIndexStatus(), 20_000);
  }

  ngOnDestroy(): void {
    this.cancelStream?.();
    if (this.statusTimer) window.clearInterval(this.statusTimer);
    if (this.saveTimer) {
      window.clearTimeout(this.saveTimer);
      this.persistCurrent();
    }
  }

  // ---- Filters / settings -------------------------------------------------
  toggleKind(kind: AssistantKind): void {
    const current = { ...this.kindFilters() };
    current[kind] = !current[kind];
    if (!Object.values(current).some(Boolean)) current[kind] = true;
    this.kindFilters.set(current);
  }

  pickSuggestion(prompt: string): void {
    this.input.set(prompt);
    queueMicrotask(() => this.composerInput?.nativeElement?.focus());
  }

  // ---- Conversation lifecycle --------------------------------------------
  newConversation(): void {
    this.cancelStream?.();
    this.cancelStream = null;
    this.messages.set([]);
    this.activeConversationId.set(null);
    this.error.set(null);
    this.isStreaming.set(false);
    this.input.set('');
    queueMicrotask(() => this.composerInput?.nativeElement?.focus());
  }

  loadConversation(id: string): void {
    if (this.activeConversationId() === id) return;
    if (this.isStreaming()) {
      this.cancelStream?.();
      this.cancelStream = null;
      this.isStreaming.set(false);
    }
    const conv = this.store.get(id);
    if (!conv) return;
    this.activeConversationId.set(id);
    const restored: ChatMessage[] = conv.messages.map(m => ({ ...m, streaming: false }));
    this.msgSeq = restored.reduce((max, m) => Math.max(max, m.id), 0);
    this.messages.set(restored);
    if (conv.settings?.kinds && conv.settings.kinds.length) {
      const next = { requirements: false, test_cases: false, design_tickets: false, specs: false } as Record<AssistantKind, boolean>;
      for (const k of conv.settings.kinds) next[k] = true;
      this.kindFilters.set(next);
    }
    if (conv.settings?.provider) this.selectedProvider.set(conv.settings.provider);
    this.error.set(null);
    this.input.set('');
  }

  deleteConversation(id: string, ev?: MouseEvent): void {
    ev?.stopPropagation();
    if (!confirm('Delete this conversation?')) return;
    this.store.delete(id);
    if (this.activeConversationId() === id) this.newConversation();
  }

  clearAllConversations(): void {
    if (!confirm('Delete every saved conversation? This cannot be undone.')) return;
    this.store.clearAll();
    this.newConversation();
  }

  startRename(conv: Conversation, ev: MouseEvent): void {
    ev.stopPropagation();
    this.renamingId.set(conv.id);
    this.renameDraft.set(conv.title);
  }

  commitRename(conv: Conversation): void {
    const next = this.renameDraft().trim();
    if (next && next !== conv.title) this.store.rename(conv.id, next);
    this.renamingId.set(null);
    this.renameDraft.set('');
  }

  cancelRename(): void {
    this.renamingId.set(null);
    this.renameDraft.set('');
  }

  toggleHistory(): void {
    this.historyOpen.update(v => !v);
  }

  trackConversation(_: number, c: Conversation): string { return c.id; }
  trackMessage(_: number, m: ChatMessage): number { return m.id; }

  private persistCurrent(): void {
    const msgs = this.messages();
    if (msgs.length === 0) return;
    const id = this.activeConversationId() ?? this.store.newId();
    const firstUser = msgs.find(m => m.role === 'user');
    const stored: StoredChatMessage[] = msgs.map(({ streaming: _streaming, copied: _copied, ...rest }) => rest);
    const existing = this.store.get(id);
    const conv: Conversation = {
      id,
      title: existing?.title || this.store.deriveTitle(firstUser?.content || 'New conversation'),
      createdAt: existing?.createdAt || Date.now(),
      updatedAt: Date.now(),
      messages: stored,
      settings: { kinds: this.selectedKinds(), provider: this.selectedProvider() || undefined },
    };
    this.store.save(conv);
    if (!this.activeConversationId()) this.activeConversationId.set(id);
  }

  // ---- RAG index actions --------------------------------------------------
  refreshIndexStatus(): void {
    this.assistant.indexStatus().subscribe({
      next: st => this.indexStatus.set(st),
      error: () => {},
    });
  }

  reindex(force = false): void {
    if (this.reindexing()) return;
    this.reindexing.set(true);
    this.reindexMsg.set(null);
    this.assistant.refreshIndex(force).subscribe({
      next: res => {
        this.indexStatus.set(res.status);
        const s = res.summary || {};
        const created = s['created'] ?? 0, updated = s['updated'] ?? 0, deleted = s['deleted'] ?? 0;
        this.reindexMsg.set(`+${created} added · ${updated} updated · ${deleted} removed`);
        this.reindexing.set(false);
      },
      error: () => {
        this.reindexing.set(false);
      },
    });
  }

  // ---- Composer -----------------------------------------------------------
  onInputKeydown(ev: KeyboardEvent): void {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      this.send();
    }
  }

  onInputChange(value: string, textarea: HTMLTextAreaElement): void {
    this.input.set(value);
    // Auto-resize
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 240) + 'px';
  }

  stop(): void {
    this.cancelStream?.();
    this.cancelStream = null;
    this.isStreaming.set(false);
    this.messages.update(list => {
      const last = list[list.length - 1];
      if (last && last.role === 'assistant' && last.streaming) last.streaming = false;
      return [...list];
    });
  }

  send(): void {
    if (this.isStreaming()) return;
    const text = this.input().trim();
    if (!text) return;

    const history = this.messages()
      .filter(m => !m.error)
      .map(m => ({ role: m.role, content: m.content }));

    const userMsg: ChatMessage = {
      id: ++this.msgSeq, role: 'user', content: text, createdAt: Date.now(),
    };
    const assistantMsg: ChatMessage = {
      id: ++this.msgSeq, role: 'assistant', content: '', streaming: true,
      citations: [], matchedTerms: [], createdAt: Date.now(),
    };

    this.messages.update(list => [...list, userMsg, assistantMsg]);
    this.input.set('');
    this.error.set(null);
    this.isStreaming.set(true);

    // Reset composer height
    if (this.composerInput?.nativeElement) {
      this.composerInput.nativeElement.style.height = 'auto';
    }

    this.cancelStream = this.assistant.stream(
      {
        question: text,
        history,
        kinds: this.selectedKinds(),
        provider: this.selectedProvider() || undefined,
      },
      {
        onMeta: meta => this.patchAssistant(assistantMsg.id, m => ({
          ...m,
          citations: meta.citations,
          matchedTerms: meta.matched_terms,
          provider: meta.provider,
          retrievalMode: meta.retrieval_mode,
        })),
        onToken: chunk => this.patchAssistant(assistantMsg.id, m => ({
          ...m,
          content: (m.content || '') + chunk,
        })),
        onDone: () => {
          this.patchAssistant(assistantMsg.id, m => ({ ...m, streaming: false }));
          this.isStreaming.set(false);
          this.cancelStream = null;
          this.persistCurrent();
        },
        onError: () => {
          this.patchAssistant(assistantMsg.id, m => ({
            ...m,
            streaming: false,
            content: m.content || this.retrievalFallback(m),
          }));
          this.isStreaming.set(false);
          this.cancelStream = null;
          this.persistCurrent();
        },
      },
    );
  }

  regenerateLast(): void {
    if (this.isStreaming()) return;
    const list = [...this.messages()];
    // Find the last user message
    let lastUserIdx = -1;
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].role === 'user') { lastUserIdx = i; break; }
    }
    if (lastUserIdx < 0) return;
    const lastUser = list[lastUserIdx];
    // Trim everything after (and including) the assistant reply
    const trimmed = list.slice(0, lastUserIdx);
    this.messages.set(trimmed);
    this.input.set(lastUser.content);
    queueMicrotask(() => this.send());
  }

  // ---- Helpers ------------------------------------------------------------
  private patchAssistant(id: number, updater: (m: ChatMessage) => ChatMessage): void {
    this.messages.update(list => list.map(m => (m.id === id ? updater(m) : m)));
  }

  goToCitation(c: AssistantCitation): void {
    if (c.route) this.router.navigateByUrl(c.route);
  }

  /**
   * Lightweight markdown-ish renderer:
   *  - Triple-backtick fenced code blocks
   *  - `inline code`
   *  - **bold**, *italic*
   *  - "- item" / "* item" turned into bullets
   *  - Inline citation IDs (REQ-001 etc.) wrapped in clickable spans
   *
   * Kept dependency-free so the bundle stays small. Order matters: escape
   * HTML first, then code blocks, then inline transforms, then citations.
   */
  renderAnswer(content: string, citations: AssistantCitation[] | undefined): string {
    if (!content) return '';
    let html = this.escapeHtml(content);

    // Fenced code blocks ``` ```
    html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_m, _lang, body) =>
      `<pre class="md-pre"><code>${body.replace(/\n$/, '')}</code></pre>`
    );

    // Inline code `...`
    html = html.replace(/(^|[^`])`([^`\n]+?)`/g, '$1<code class="md-code">$2</code>');

    // Headings (# .. ####) — must run before bold/italic
    html = html.replace(/^(#{1,4})\s+([^\n]+)$/gm, (_m, hashes: string, text: string) => {
      const level = Math.min(hashes.length, 4);
      return `<h${level}>${text.trim()}</h${level}>`;
    });

    // Blockquotes — group consecutive "> " lines
    html = html.replace(/(?:^|\n)((?:&gt;\s?[^\n]*\n?)+)/g, (_m, block: string) => {
      const inner = block.trim().split('\n').map(l => l.replace(/^&gt;\s?/, '')).join('<br>');
      return `\n<blockquote><p>${inner}</p></blockquote>`;
    });

    // Bold **...** then italic *...* (italic guarded so it doesn't eat list bullets)
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');

    // Ordered lists — consecutive "1. " / "2. " lines
    html = html.replace(/(?:^|\n)((?:\d+\.\s+[^\n]+\n?)+)/g, (_m, block: string) => {
      const items = block.trim().split('\n').map(l => l.replace(/^\d+\.\s+/, ''));
      return '\n<ol class="md-list md-ol">' + items.map(i => `<li>${i}</li>`).join('') + '</ol>';
    });

    // Unordered lists — consecutive "- " / "* " lines
    html = html.replace(/(?:^|\n)((?:[-*] [^\n]+\n?)+)/g, (_match, block: string) => {
      const items = block.trim().split('\n').map(l => l.replace(/^[-*]\s+/, ''));
      return '\n<ul class="md-list">' + items.map(i => `<li>${i}</li>`).join('') + '</ul>';
    });

    // Paragraph breaks — preserve double newlines, single newlines become <br>
    html = html.replace(/\n{2,}/g, '</p><p>');
    html = `<p>${html}</p>`.replace(/\n/g, '<br>');
    // Strip <p> wrappers around block elements introduced above
    html = html.replace(/<p>(\s*<(?:ul|ol|pre|h[1-4]|blockquote)[\s\S]*?<\/(?:ul|ol|pre|h[1-4]|blockquote)>)\s*<\/p>/g, '$1');
    // Remove stray <br> immediately before/after block elements
    html = html.replace(/<br>\s*(<(?:ul|ol|pre|h[1-4]|blockquote))/g, '$1');
    html = html.replace(/(<\/(?:ul|ol|pre|h[1-4]|blockquote)>)\s*<br>/g, '$1');
    // Drop empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');

    if (!citations?.length) return html;

    // Inline citation chips (REQ-001 → clickable). Skip if the same id appears
    // inside an existing tag attribute.
    const seen = new Set<string>();
    for (const c of citations) {
      if (!c.id || seen.has(c.id)) continue;
      seen.add(c.id);
      const safeId = c.id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const pattern = new RegExp(`(\\[?)\\b(${safeId})\\b(\\]?)(?![^<]*>)`, 'g');
      const safeTitle = (c.title || '').replace(/"/g, '&quot;');
      html = html.replace(pattern, (_match, lb, id, rb) =>
        `${lb}<a class="cite-inline" data-route="${c.route}" title="${safeTitle}">${id}</a>${rb}`
      );
    }
    return html;
  }

  onAnswerClick(ev: MouseEvent): void {
    const target = ev.target as HTMLElement | null;
    if (!target) return;
    const link = target.closest('a.cite-inline') as HTMLAnchorElement | null;
    if (!link) return;
    ev.preventDefault();
    const route = link.getAttribute('data-route');
    if (route) this.router.navigateByUrl(route);
  }

  async copyMessage(m: ChatMessage): Promise<void> {
    try {
      await navigator.clipboard.writeText(m.content || '');
      this.patchAssistant(m.id, x => ({ ...x, copied: true }));
      window.setTimeout(() => this.patchAssistant(m.id, x => ({ ...x, copied: false })), 1500);
    } catch {
      // ignore — clipboard permission denied / unavailable
    }
  }

  relativeTime(ts: number): string {
    this.i18n.currentLang();
    const diff = Date.now() - ts;
    if (diff < 60_000) return this.i18n.translateLiteral('just now');
    if (diff < 3_600_000) return this.i18n.translateLiteral(`${Math.round(diff / 60_000)}m ago`);
    if (diff < 86_400_000) return this.i18n.translateLiteral(`${Math.round(diff / 3_600_000)}h ago`);
    return new Date(ts).toLocaleDateString(this.i18n.currentLang() === 'ja' ? 'ja-JP' : undefined);
  }

  private retrievalFallback(m: ChatMessage): string {
    const cites = m.citations;
    if (!cites?.length) return 'No matching items were found in the selected sources.';
    const lines = cites.slice(0, 12).map(c => `- [${c.id}] ${c.title}`);
    const tail = cites.length > 12 ? `\n- …and ${cites.length - 12} more (see Sources below)` : '';
    return `Here are the matching items I found:\n${lines.join('\n')}${tail}`;
  }

  private escapeHtml(s: string): string {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}
