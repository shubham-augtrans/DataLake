import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ConfigService } from '../../services/config.service';

export interface WidgetSummary {
  title: string;
  sql?: string;
  row_count?: number;
  duration_ms?: number;
  chart_type?: string | null;
  error?: string | null;
}

export interface GenerateResponse {
  prompt: string;
  dashboard_url: string;
  embed_url: string | null;
  widgets: WidgetSummary[];
}

const EXAMPLE_PROMPTS = [
  'Show average pressure per machine',
  'Show total readings per machine',
  'Show the 10 most recent readings'
];

@Component({
  selector: 'app-playground',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    ProgressSpinnerModule
  ],
  templateUrl: './playground.component.html',
  styleUrl: './playground.component.css'
})
export class PlaygroundComponent {

  constructor(
    private configService: ConfigService,
    private sanitizer: DomSanitizer
  ) {}

  examplePrompts = EXAMPLE_PROMPTS;

  prompt = '';
  generating = false;
  errorMessage = '';

  result: GenerateResponse | null = null;
  embedSrc: SafeResourceUrl | null = null;

  useExample(example: string): void {
    this.prompt = example;
  }

  get canGenerate(): boolean {
    return !!this.prompt.trim() && !this.generating;
  }

  generate(): void {
    if (!this.canGenerate) {
      return;
    }

    this.generating = true;
    this.errorMessage = '';
    this.result = null;
    this.embedSrc = null;

    this.configService.post('/playground/generate/', {
      prompt: this.prompt
    }).subscribe({
      next: (response: GenerateResponse) => {
        this.generating = false;
        this.result = response;
        this.embedSrc = response.embed_url
          ? this.sanitizer.bypassSecurityTrustResourceUrl(response.embed_url)
          : null;
      },
      error: (error) => {
        this.generating = false;
        this.errorMessage = error?.error?.error || 'Failed to build a dashboard for this prompt.';
      }
    });
  }
}
