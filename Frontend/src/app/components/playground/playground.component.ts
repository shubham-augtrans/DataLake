import { CommonModule } from '@angular/common';
import { AfterViewChecked, Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ButtonModule } from 'primeng/button';
import { DropdownModule } from 'primeng/dropdown';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TableModule } from 'primeng/table';

import Chart from 'chart.js/auto';

import { ConfigService } from '../../services/config.service';

export interface DataSourceOption {
  id: number;
  name: string;
  source_type: string;
}

export interface ChartSpec {
  type: 'bar' | 'line' | 'number' | 'table';
  x_field: string | null;
  y_field: string | null;
}

export interface GenerateResponse {
  prompt: string;
  sql: string;
  columns: string[];
  rows: any[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
  chart: ChartSpec;
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
    ProgressSpinnerModule,
    TableModule
  ],
  templateUrl: './playground.component.html',
  styleUrl: './playground.component.css'
})
export class PlaygroundComponent implements OnInit, AfterViewChecked {

  @ViewChild('chartCanvas') chartCanvasRef?: ElementRef<HTMLCanvasElement>;

  constructor(private configService: ConfigService) {}

  examplePrompts = EXAMPLE_PROMPTS;

  postgresSources: DataSourceOption[] = [];
  selectedSourceId: number | null = null;

  prompt = '';
  generating = false;
  errorMessage = '';

  result: GenerateResponse | null = null;
  tableRows: Record<string, any>[] = [];

  private chart: Chart | null = null;
  private chartNeedsRender = false;

  ngOnInit(): void {
    this.loadPostgresSources();
  }

  ngAfterViewChecked(): void {
    if (this.chartNeedsRender && this.chartCanvasRef) {
      this.chartNeedsRender = false;
      this.renderChart();
    }
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
    this.destroyChart();

    this.configService.post('/playground/generate/', {
      data_source: this.selectedSourceId,
      prompt: this.prompt
    }).subscribe({
      next: (response: GenerateResponse) => {
        this.generating = false;
        this.result = response;

        this.tableRows = response.rows.map(row => {
          const record: Record<string, any> = {};
          response.columns.forEach((col, i) => record[col] = row[i]);
          return record;
        });

        if (response.chart.type === 'bar' || response.chart.type === 'line') {
          this.chartNeedsRender = true;
        }
      },
      error: (error) => {
        this.generating = false;
        this.errorMessage = error?.error?.error || 'Failed to generate a dashboard for this prompt.';
      }
    });
  }

  private renderChart(): void {
    if (!this.result || !this.chartCanvasRef) {
      return;
    }

    const { chart, columns, rows } = this.result;
    if (!chart.x_field || !chart.y_field) {
      return;
    }

    const xIndex = columns.indexOf(chart.x_field);
    const yIndex = columns.indexOf(chart.y_field);

    const labels = rows.map(row => String(row[xIndex]));
    const data = rows.map(row => Number(row[yIndex]));

    this.chart = new Chart(this.chartCanvasRef.nativeElement, {
      type: chart.type === 'line' ? 'line' : 'bar',
      data: {
        labels,
        datasets: [{
          label: chart.y_field,
          data,
          backgroundColor: 'rgba(180, 197, 255, 0.5)',
          borderColor: '#b4c5ff',
          borderWidth: 2,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#c3c6d8' } }
        },
        scales: {
          x: { ticks: { color: '#c3c6d8' }, grid: { color: '#2a2d3a' } },
          y: { ticks: { color: '#c3c6d8' }, grid: { color: '#2a2d3a' } }
        }
      }
    });
  }

  private destroyChart(): void {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}
