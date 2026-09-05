import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { DropdownModule } from 'primeng/dropdown';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TableModule } from 'primeng/table';
import { TooltipModule } from 'primeng/tooltip';

import { ConfigService } from '../../services/config.service';

export interface DataSourceOption {
  id: number;
  name: string;
  source_type: string;
}

export interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
}

export interface QueryHistoryItem {
  id: number;
  data_source: number;
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
    DialogModule,
    DropdownModule,
    InputTextModule,
    PasswordModule,
    ProgressSpinnerModule,
    TableModule,
    TooltipModule
  ],
  templateUrl: './query.component.html',
  styleUrl: './query.component.css'
})
export class QueryComponent implements OnInit {

  constructor(private configService: ConfigService) {}

  postgresSources: DataSourceOption[] = [];
  selectedSourceId: number | null = null;

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

  connectionDialogVisible = false;
  savingConnection = false;
  connectionError = '';

  connectionForm = {
    name: '',
    host: '',
    port: '5432',
    database: '',
    username: '',
    password: ''
  };

  ngOnInit(): void {
    this.loadPostgresSources();
    this.loadHistory();
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
    return !!this.selectedSourceId && !!this.sqlText.trim() && !this.running;
  }

  newQuery(): void {
    this.sqlText = '';
    this.hasRun = false;
    this.errorMessage = '';
    this.resultColumns = [];
    this.resultRows = [];
  }

  runQuery(): void {
    if (!this.canRun || !this.selectedSourceId) {
      return;
    }

    this.running = true;
    this.errorMessage = '';

    this.configService.post('/query/execute/', {
      data_source: this.selectedSourceId,
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
    this.selectedSourceId = item.data_source;
  }

  get isConnectionFormValid(): boolean {
    const f = this.connectionForm;
    return !!(f.name.trim() && f.host.trim() && f.port.trim() && f.database.trim() && f.username.trim() && f.password);
  }

  openConnectionDialog(): void {
    this.connectionError = '';
    this.connectionForm = { name: '', host: '', port: '5432', database: '', username: '', password: '' };
    this.connectionDialogVisible = true;
  }

  closeConnectionDialog(): void {
    this.connectionDialogVisible = false;
  }

  saveConnection(): void {
    if (!this.isConnectionFormValid) {
      return;
    }

    this.savingConnection = true;
    this.connectionError = '';

    const payload = {
      name: this.connectionForm.name.trim(),
      source_type: 'postgres',
      description: '',
      is_active: true,
      configuration: {
        host: this.connectionForm.host.trim(),
        port: this.connectionForm.port.trim(),
        database: this.connectionForm.database.trim(),
        username: this.connectionForm.username.trim(),
        password: this.connectionForm.password
      }
    };

    this.configService.post('/data-sources/', payload).subscribe({
      next: (created: DataSourceOption) => {
        this.savingConnection = false;
        this.connectionDialogVisible = false;
        this.loadPostgresSources();
        this.selectedSourceId = created.id;
      },
      error: (error) => {
        this.savingConnection = false;
        this.connectionError = error?.error?.detail || 'Failed to create connection.';
      }
    });
  }
}
