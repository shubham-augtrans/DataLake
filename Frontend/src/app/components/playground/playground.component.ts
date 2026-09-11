import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { ConfigService } from '../../services/config.service';

export interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  isError?: boolean;
}

export interface HistoryTurn {
  prompt: string;
  sql: string;
}

export interface ChatResponse {
  prompt: string;
  answer: string;
  sql: string | null;
  is_chat_only: boolean;
  // Only present when is_chat_only is false
  row_count?: number;
  duration_ms?: number;
  chart_type?: string;
  dashboard_url?: string;
  embed_url?: string | null;
  card_id?: number;
  dashboard_id?: number;
  bi_tool?: 'METABASE' | 'SUPERSET';
  updated_existing?: boolean;
}

export interface ChartTile {
  id: number;
  prompt: string;
  chartType: string;
  dashboardUrl: string;
  embedUrl: string | null;
  // Sanitized once when embedUrl is set/changed - never recomputed in the
  // template, otherwise every change-detection pass (e.g. each keystroke in
  // the prompt box) hands the iframe a "new" SafeResourceUrl and it reloads.
  embedSrc: SafeResourceUrl | null;
  rowCount: number;
  durationMs: number;
  cardId: number;
  dashboardId: number;
  // Which BI backend this dashboard actually lives in (whatever the
  // user's Settings preference was at creation time) - a dashboard/card id
  // from one tool means nothing to the other, so follow-up edits must keep
  // targeting the same one even if the user later switches tools.
  biTool: 'METABASE' | 'SUPERSET';
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  history: HistoryTurn[];
  tiles: ChartTile[];
  updatedAt: number;
}

const EXAMPLE_PROMPTS = [
  'Show average pressure per machine',
  'Show total readings per machine',
  'Show the 10 most recent readings'
];

const STORAGE_KEY = 'playground-conversations';

let nextTileId = 1;

function makeConversationId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function emptyConversation(): Conversation {
  return {
    id: makeConversationId(),
    title: 'New conversation',
    messages: [],
    history: [],
    tiles: [],
    updatedAt: Date.now()
  };
}

@Component({
  selector: 'app-playground',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './playground.component.html',
  styleUrl: './playground.component.css'
})
export class PlaygroundComponent implements OnInit {

  constructor(
    private configService: ConfigService,
    private sanitizer: DomSanitizer
  ) {}

  examplePrompts = EXAMPLE_PROMPTS;

  prompt = '';
  sending = false;

  // All past + current conversations - persisted to localStorage so a
  // reload (or picking an older thread) doesn't lose anything, ChatGPT-style.
  conversations: Conversation[] = [];
  activeId = '';

  // The active conversation's data, mirrored onto plain fields so the
  // template (and existing send()/tiles logic) can keep binding directly
  // to messages/history/tiles.
  messages: ChatMessage[] = [];
  history: HistoryTurn[] = [];
  tiles: ChartTile[] = [];

  // Full-size modal view of one tile
  modalTile: ChartTile | null = null;

  ngOnInit(): void {
    this.conversations = this.loadConversations();

    if (this.conversations.length === 0) {
      this.conversations = [emptyConversation()];
    }

    this.activateConversation(this.conversations[0].id);
  }

  private loadConversations(): Conversation[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  private persist(): void {
    this.syncActiveIntoList();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.conversations));
    } catch {
      // Storage full or unavailable - conversations just won't survive a reload.
    }
  }

  private syncActiveIntoList(): void {
    const active = this.conversations.find(c => c.id === this.activeId);
    if (!active) {
      return;
    }
    active.messages = this.messages;
    active.history = this.history;
    active.tiles = this.tiles;
    active.updatedAt = Date.now();

    const firstUserMessage = this.messages.find(m => m.role === 'user');
    if (firstUserMessage) {
      active.title = firstUserMessage.text.slice(0, 48);
    }
  }

  activateConversation(id: string): void {
    this.syncActiveIntoList();

    const conversation = this.conversations.find(c => c.id === id);
    if (!conversation) {
      return;
    }

    this.activeId = conversation.id;
    this.messages = conversation.messages;
    this.history = conversation.history;
    this.tiles = conversation.tiles;
    this.rehydrateTiles(this.tiles);
    this.modalTile = null;
  }

  get activeTitle(): string {
    return this.conversations.find(c => c.id === this.activeId)?.title || 'New conversation';
  }

  private sanitizeUrl(url: string | null): SafeResourceUrl | null {
    return url ? this.sanitizer.bypassSecurityTrustResourceUrl(url) : null;
  }

  private rehydrateTiles(tiles: ChartTile[]): void {
    // embedSrc doesn't survive JSON (localStorage) round-tripping - rebuild
    // it from the plain embedUrl string whenever a conversation is loaded.
    for (const tile of tiles) {
      tile.embedSrc = this.sanitizeUrl(tile.embedUrl);
    }
  }

  useExample(example: string): void {
    this.prompt = example;
  }

  get canSend(): boolean {
    return !!this.prompt.trim() && !this.sending;
  }

  send(): void {
    if (!this.canSend) {
      return;
    }

    const submittedPrompt = this.prompt.trim();
    this.prompt = '';
    this.sending = true;

    this.messages = [...this.messages, { role: 'user', text: submittedPrompt }];
    this.persist();

    // If the user just wants the last chart re-rendered differently
    // ("same data as a pie chart"), the backend updates that dashboard in
    // place instead of creating a new one - it needs to know which one.
    const lastTile = this.tiles[this.tiles.length - 1];

    this.configService.post('/playground/chat/', {
      prompt: submittedPrompt,
      history: this.history,
      previous_card_id: lastTile?.cardId ?? null,
      previous_dashboard_id: lastTile?.dashboardId ?? null,
      previous_embed_url: lastTile?.embedUrl ?? null,
      previous_bi_tool: lastTile?.biTool ?? null
    }).subscribe({
      next: (response: ChatResponse) => {
        this.sending = false;

        // Only turns that actually ran a query get added to the SQL
        // grounding context - a pure "thanks" reply has none.
        if (response.sql) {
          this.history = [...this.history, { prompt: response.prompt, sql: response.sql }];
        }

        if (!response.is_chat_only) {
          if (response.updated_existing && lastTile) {
            // Same dashboard either way - either the existing chart was
            // replaced in place, or a new chart was added alongside it
            // (both land on the same embedded dashboard, so the one tile
            // just needs to reload). Either way, further edits ("now make
            // it a line chart") should target whichever card this turn
            // touched, so track its id going forward.
            // An edit turn (rename/recolor/resize/move) doesn't re-run the
            // query, so chart_type/row_count/duration_ms come back absent -
            // keep whatever the tile already had instead of blanking it out.
            const baseEmbedUrl = (lastTile.embedUrl || '').split('?')[0];
            lastTile.cardId = response.card_id!;
            lastTile.chartType = response.chart_type ?? lastTile.chartType;
            lastTile.rowCount = response.row_count ?? lastTile.rowCount;
            lastTile.durationMs = response.duration_ms ?? lastTile.durationMs;
            lastTile.prompt = response.prompt;
            lastTile.embedUrl = baseEmbedUrl ? `${baseEmbedUrl}?t=${Date.now()}` : lastTile.embedUrl;
            lastTile.embedSrc = this.sanitizeUrl(lastTile.embedUrl);
            this.tiles = [...this.tiles];
          } else {
            const tile: ChartTile = {
              id: nextTileId++,
              prompt: response.prompt,
              chartType: response.chart_type!,
              dashboardUrl: response.dashboard_url!,
              embedUrl: response.embed_url ?? null,
              embedSrc: this.sanitizeUrl(response.embed_url ?? null),
              rowCount: response.row_count!,
              durationMs: response.duration_ms!,
              cardId: response.card_id!,
              dashboardId: response.dashboard_id!,
              biTool: response.bi_tool ?? 'METABASE'
            };

            // First chart of the conversation - every one after this replaces it.
            this.tiles = [tile];
          }
        }
        // is_chat_only: answer goes in the chat only, dashboard untouched.

        this.messages = [
          ...this.messages,
          { role: 'assistant', text: response.answer || `Here's your ${response.chart_type} chart — ${response.row_count} row${response.row_count === 1 ? '' : 's'}.` }
        ];

        this.persist();
      },
      error: (error) => {
        this.sending = false;
        // The backend error is a raw Trino/LLM exception - useful for
        // debugging, not for a chat bubble, so it only goes to the console.
        console.error('Playground chat request failed:', error?.error?.error || error);
        this.messages = [
          ...this.messages,
          { role: 'assistant', text: 'Sorry, I couldn\'t build that chart. Try rephrasing your question?', isError: true }
        ];
        this.persist();
      }
    });
  }

  toolLabel(biTool: 'METABASE' | 'SUPERSET' | undefined): string {
    return biTool === 'SUPERSET' ? 'Superset' : 'Metabase';
  }

  openModal(tile: ChartTile): void {
    this.modalTile = tile;
  }

  closeModal(): void {
    this.modalTile = null;
  }

  newConversation(): void {
    this.syncActiveIntoList();

    const fresh = emptyConversation();
    this.conversations = [fresh, ...this.conversations];
    this.activeId = fresh.id;
    this.messages = fresh.messages;
    this.history = fresh.history;
    this.tiles = fresh.tiles;
    this.prompt = '';
    this.modalTile = null;

    this.persist();
  }

  deleteConversation(id: string, event: Event): void {
    event.stopPropagation();

    this.conversations = this.conversations.filter(c => c.id !== id);

    if (this.conversations.length === 0) {
      this.conversations = [emptyConversation()];
    }

    if (id === this.activeId) {
      const next = this.conversations[0];
      this.activeId = next.id;
      this.messages = next.messages;
      this.history = next.history;
      this.tiles = next.tiles;
      this.rehydrateTiles(this.tiles);
      this.modalTile = null;
    }

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.conversations));
    } catch {
      // ignore
    }
  }
}
