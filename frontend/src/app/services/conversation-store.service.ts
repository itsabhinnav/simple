import { Injectable, computed, signal } from '@angular/core';
import { AssistantCitation, AssistantKind } from './assistant.service';

export interface StoredChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  citations?: AssistantCitation[];
  matchedTerms?: string[];
  provider?: string;
  retrievalMode?: 'hybrid' | 'vector' | 'lexical';
  error?: boolean;
  createdAt: number;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: StoredChatMessage[];
  settings?: {
    kinds?: AssistantKind[];
    provider?: string;
  };
}

const STORAGE_KEY = 'sakura.assistant.conversations.v1';
const MAX_TITLE_LENGTH = 60;
const MAX_CONVERSATIONS = 100;

@Injectable({ providedIn: 'root' })
export class ConversationStore {
  private _list = signal<Conversation[]>(this.load());

  list = this._list.asReadonly();
  ordered = computed(() => [...this._list()].sort((a, b) => b.updatedAt - a.updatedAt));

  count = computed(() => this._list().length);

  get(id: string): Conversation | undefined {
    return this._list().find(c => c.id === id);
  }

  save(conversation: Conversation): void {
    const next = [...this._list()];
    const idx = next.findIndex(c => c.id === conversation.id);
    if (idx >= 0) next[idx] = conversation;
    else next.unshift(conversation);
    // Cap to keep localStorage healthy
    const trimmed = next.slice(0, MAX_CONVERSATIONS);
    this._list.set(trimmed);
    this.persist();
  }

  rename(id: string, title: string): void {
    const next = this._list().map(c =>
      c.id === id ? { ...c, title: title.trim() || c.title, updatedAt: Date.now() } : c
    );
    this._list.set(next);
    this.persist();
  }

  delete(id: string): void {
    this._list.set(this._list().filter(c => c.id !== id));
    this.persist();
  }

  clearAll(): void {
    this._list.set([]);
    this.persist();
  }

  newId(): string {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID();
    }
    return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
  }

  deriveTitle(firstUserMessage: string): string {
    const cleaned = firstUserMessage.replace(/\s+/g, ' ').trim();
    if (cleaned.length <= MAX_TITLE_LENGTH) return cleaned || 'New conversation';
    return cleaned.slice(0, MAX_TITLE_LENGTH - 1).trimEnd() + '…';
  }

  private load(): Conversation[] {
    if (typeof localStorage === 'undefined') return [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter(c => c && typeof c.id === 'string' && Array.isArray(c.messages));
    } catch {
      return [];
    }
  }

  private persist(): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this._list()));
    } catch (err) {
      console.warn('ConversationStore: failed to persist (likely quota)', err);
    }
  }
}
