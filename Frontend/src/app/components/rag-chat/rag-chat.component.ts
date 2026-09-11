import { CommonModule } from '@angular/common';
import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonModule } from 'primeng/button';
import { CheckboxModule } from 'primeng/checkbox';

import { ConfigService } from '../../services/config.service';

export interface RagDocument {
  pipeline_id: number;
  name: string;
  filename: string;
  source_name: string;
  chunk_count: number;
}

export interface RagSource {
  pipeline_id: number;
  pipeline_name: string;
  page_number: number | null;
  score: number;
  snippet: string;
}

export interface ChatTurn {
  question: string;
  answer: string;
  sources: RagSource[];
  error?: boolean;
}

@Component({
  selector: 'app-rag-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, CheckboxModule],
  templateUrl: './rag-chat.component.html',
  styleUrl: './rag-chat.component.css'
})
export class RagChatComponent implements OnInit {

  @ViewChild('threadEnd') threadEnd?: ElementRef<HTMLDivElement>;

  documents: RagDocument[] = [];
  selectedPipelineIds = new Set<number>();
  documentsLoading = true;
  documentsError = '';

  turns: ChatTurn[] = [];
  question = '';
  asking = false;
  askError = '';

  // How many previous turns to send as context - bounded so the prompt
  // doesn't grow without limit over a long session.
  private readonly MAX_HISTORY_TURNS = 6;

  constructor(private configService: ConfigService) {}

  ngOnInit(): void {
    this.loadDocuments();
  }

  loadDocuments(): void {
    this.documentsLoading = true;
    this.documentsError = '';

    this.configService.get('/rag/documents/').subscribe({
      next: (docs: RagDocument[]) => {
        this.documents = Array.isArray(docs) ? docs : [];
        this.documentsLoading = false;
      },
      error: () => {
        this.documentsError = 'Could not load PDF documents.';
        this.documentsLoading = false;
      }
    });
  }

  toggleDocument(pipelineId: number): void {
    if (this.selectedPipelineIds.has(pipelineId)) {
      this.selectedPipelineIds.delete(pipelineId);
    } else {
      this.selectedPipelineIds.add(pipelineId);
    }
  }

  isSelected(pipelineId: number): boolean {
    return this.selectedPipelineIds.has(pipelineId);
  }

  get scopeLabel(): string {
    if (this.selectedPipelineIds.size === 0) {
      return 'Searching across all ingested PDFs';
    }
    return `Searching ${this.selectedPipelineIds.size} selected PDF${this.selectedPipelineIds.size > 1 ? 's' : ''}`;
  }

  askQuestion(): void {
    const question = this.question.trim();
    if (!question || this.asking) {
      return;
    }

    this.asking = true;
    this.askError = '';
    this.question = '';

    const history = this.turns
      .filter(t => !t.error)
      .slice(-this.MAX_HISTORY_TURNS)
      .map(t => ({ question: t.question, answer: t.answer }));

    const payload = {
      question,
      pipeline_ids: Array.from(this.selectedPipelineIds),
      history
    };

    this.configService.post('/rag/chat/', payload).subscribe({
      next: (response: { answer: string; sources: RagSource[] }) => {
        this.turns.push({ question, answer: response.answer, sources: response.sources || [] });
        this.asking = false;
        this.scrollToBottom();
      },
      error: (error) => {
        const message = error?.error?.error || 'Something went wrong answering that question.';
        this.turns.push({ question, answer: message, sources: [], error: true });
        this.asking = false;
        this.scrollToBottom();
      }
    });
  }

  onEnter(event: Event): void {
    event.preventDefault();
    this.askQuestion();
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      this.threadEnd?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, 0);
  }
}
