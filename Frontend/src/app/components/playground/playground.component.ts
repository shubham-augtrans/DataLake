import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
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
  sql: string;
  row_count: number;
  duration_ms: number;
  chart_type: string;
  dashboard_url: string;
  embed_url: string | null;
}

export interface ChartTile {
  id: number;
  prompt: string;
  chartType: string;
  dashboardUrl: string;
  embedSrc: SafeResourceUrl | null;
  rowCount: number;
  durationMs: number;
}

const EXAMPLE_PROMPTS = [
  'Show average pressure per machine',
  'Show total readings per machine',
  'Show the 10 most recent readings'
];

const MAX_TILES = 4;

let nextTileId = 1;

@Component({
  selector: 'app-playground',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './playground.component.html',
  styleUrl: './playground.component.css'
})
export class PlaygroundComponent {

  constructor(
    private configService: ConfigService,
    private sanitizer: DomSanitizer
  ) {}

  examplePrompts = EXAMPLE_PROMPTS;

  // Floating chat widget state
  chatOpen = false;
  prompt = '';
  sending = false;
  messages: ChatMessage[] = [];

  // Conversation context sent with every request - each entry is a turn
  // that actually produced a chart, so a follow-up can either inherit
  // context ("now show it for machine X too") or explicitly reuse the
  // exact same data ("same data as a pie chart").
  history: HistoryTurn[] = [];

  // The chart canvas - up to 4 tiles on screen at once, oldest evicted
  // first once full.
  tiles: ChartTile[] = [];

  // Full-size modal view of one tile
  modalTile: ChartTile | null = null;

  toggleChat(): void {
    this.chatOpen = !this.chatOpen;
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

    this.configService.post('/playground/chat/', {
      prompt: submittedPrompt,
      history: this.history
    }).subscribe({
      next: (response: ChatResponse) => {
        this.sending = false;

        this.history = [...this.history, { prompt: response.prompt, sql: response.sql }];

        const tile: ChartTile = {
          id: nextTileId++,
          prompt: response.prompt,
          chartType: response.chart_type,
          dashboardUrl: response.dashboard_url,
          embedSrc: response.embed_url
            ? this.sanitizer.bypassSecurityTrustResourceUrl(response.embed_url)
            : null,
          rowCount: response.row_count,
          durationMs: response.duration_ms
        };

        this.tiles = [...this.tiles, tile].slice(-MAX_TILES);

        this.messages = [
          ...this.messages,
          { role: 'assistant', text: `Here's your ${response.chart_type} chart — ${response.row_count} row${response.row_count === 1 ? '' : 's'}.` }
        ];
      },
      error: (error) => {
        this.sending = false;
        // The backend error is a raw Trino/Ollama exception - useful for
        // debugging, not for a chat bubble, so it only goes to the console.
        console.error('Playground chat request failed:', error?.error?.error || error);
        this.messages = [
          ...this.messages,
          { role: 'assistant', text: 'Sorry, I couldn\'t build that chart. Try rephrasing your question?', isError: true }
        ];
      }
    });
  }

  openModal(tile: ChartTile): void {
    this.modalTile = tile;
  }

  closeModal(): void {
    this.modalTile = null;
  }

  newConversation(): void {
    this.messages = [];
    this.history = [];
    this.tiles = [];
    this.prompt = '';
    this.modalTile = null;
  }
}
