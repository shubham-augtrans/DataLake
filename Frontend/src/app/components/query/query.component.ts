import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TableModule } from 'primeng/table';
import { TooltipModule } from 'primeng/tooltip';

import { ConfigService } from '../../services/config.service';

export interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
}

export interface QueryHistoryItem {
  id: number;
  data_source_name: string;
  sql_text: string;
  status: 'success' | 'error';
  row_count: number | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
}

@Component({
  selector: 'app-query',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    ButtonModule,
    ProgressSpinnerModule,
    TableModule,
    TooltipModule
  ],
  templateUrl: './query.component.html',
  styleUrl: './query.component.css'
})
export class QueryComponent implements OnInit {

  constructor(private configService: ConfigService) {}

  sqlText = 'SELECT 1;';

  running = false;
  hasRun = false;
  resultColumns: string[] = [];
  resultRows: Record<string, any>[] = [];
  rowCount = 0;
  durationMs = 0;
  truncated = false;
  errorMessage = '';

  history: QueryHistoryItem[] = [];

  ngOnInit(): void {
    this.loadHistory();
  }

  loadHistory(): void {
    this.configService.get('/query/history/').subscribe({
      next: (response: QueryHistoryItem[]) => {
        this.history = Array.isArray(response) ? response.slice(0, 10) : [];
      },
      error: (error) => {
        console.error('Failed to load query history', error);
      }
    });
  }

  get canRun(): boolean {
    return !!this.sqlText.trim() && !this.running;
  }

  newQuery(): void {
    this.sqlText = '';
    this.hasRun = false;
    this.errorMessage = '';
    this.resultColumns = [];
    this.resultRows = [];
  }

  runQuery(): void {
    if (!this.canRun) {
      return;
    }

    this.running = true;
    this.errorMessage = '';

    this.configService.post('/query/execute/', {
      sql: this.sqlText
    }).subscribe({
      next: (result: QueryResult) => {
        this.running = false;
        this.hasRun = true;
        this.resultColumns = result.columns;
        this.resultRows = result.rows.map(row => {
          const record: Record<string, any> = {};
          result.columns.forEach((col, i) => record[col] = row[i]);
          return record;
        });
        this.rowCount = result.row_count;
        this.durationMs = result.duration_ms;
        this.truncated = result.truncated;
        this.loadHistory();
      },
      error: (error) => {
        this.running = false;
        this.hasRun = true;
        this.resultColumns = [];
        this.resultRows = [];
        this.rowCount = 0;
        this.errorMessage = error?.error?.error || 'Failed to run query.';
        this.loadHistory();
      }
    });
  }

  onEditorKeydown(event: KeyboardEvent): void {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      this.runQuery();
    }
  }

  useHistoryItem(item: QueryHistoryItem): void {
    this.sqlText = item.sql_text;
  }
}
