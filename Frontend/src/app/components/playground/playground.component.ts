import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ButtonModule } from 'primeng/button';
import { DropdownModule } from 'primeng/dropdown';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ConfigService } from '../../services/config.service';

export interface DataSourceOption {
  id: number;
  name: string;
  source_type: string;
}

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
    RouterLink,
    ButtonModule,
    DropdownModule,
    ProgressSpinnerModule
  ],
  templateUrl: './playground.component.html',
  styleUrl: './playground.component.css'
})
export class PlaygroundComponent implements OnInit {

  constructor(private configService: ConfigService) {}

  examplePrompts = EXAMPLE_PROMPTS;

  postgresSources: DataSourceOption[] = [];
  selectedSourceId: number | null = null;

  prompt = '';
  generating = false;
  errorMessage = '';

  result: GenerateResponse | null = null;

  ngOnInit(): void {
    this.loadPostgresSources();
  }

  loadPostgresSources(): void {
    this.configService.get('/data-sources/').subscribe({
      next: (response: DataSourceOption[]) => {
        this.postgresSources = Array.isArray(response)
          ? response.filter(s => s.source_type === 'postgres')
          : [];

        if (this.postgresSources.length > 0 && this.selectedSourceId === null) {
          this.selectedSourceId = this.postgresSources[0].id;
        }
      },
      error: (error) => {
        console.error('Failed to load data sources', error);
      }
    });
  }

  useExample(example: string): void {
    this.prompt = example;
  }

  get canGenerate(): boolean {
    return !!this.selectedSourceId && !!this.prompt.trim() && !this.generating;
  }

  generate(): void {
    if (!this.canGenerate) {
      return;
    }

    this.generating = true;
    this.errorMessage = '';
    this.result = null;

    this.configService.post('/playground/generate/', {
      data_source: this.selectedSourceId,
      prompt: this.prompt
    }).subscribe({
      next: (response: GenerateResponse) => {
        this.generating = false;
        this.result = response;
      },
      error: (error) => {
        this.generating = false;
        this.errorMessage = error?.error?.error || 'Failed to build a dashboard for this prompt.';
      }
    });
  }
}
