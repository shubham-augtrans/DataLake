import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TableModule } from 'primeng/table';
import { TooltipModule } from 'primeng/tooltip';

import { ConfigService } from '../../services/config.service';
import { AuthenticationService } from '../../services/authentication.service';

export interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
}

export interface QueryHistoryItem {
  id: number;
  trino_user: string | null;
  sql_text: string;
  status: 'success' | 'error' | 'denied';
  row_count: number | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
}

/**
 * One node in the catalog -> schema -> table explorer tree. Kept flat
 * (parent-referencing) rather than nested so the template can render it
 * with a simple *ngFor per level without recursive components.
 */
export interface ExplorerNode {
  type: 'catalog' | 'schema' | 'table';
  name: string;
  catalog?: string;
  schema?: string;
  expanded: boolean;
  loading: boolean;
  loaded: boolean;
  error?: string;
  children: ExplorerNode[];
}

@Component({
  selector: 'app-trino-query',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    ProgressSpinnerModule,
    TableModule,
    TooltipModule
  ],
  templateUrl: './trino-query.component.html',
  styleUrl: './trino-query.component.css'
})
export class TrinoQueryComponent implements OnInit {

  constructor(
    private configService: ConfigService,
    private authService: AuthenticationService
  ) {}

  trinoUser = '';

  explorerLoading = false;
  explorerError = '';
  catalogs: ExplorerNode[] = [];

  sqlText = 'SHOW SCHEMAS FROM iceberg;';

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
    const user = this.authService.getUser();
    this.trinoUser = user?.email ? user.email.split('@')[0] : '';

    this.loadCatalogs();
    this.loadHistory();
  }

  get canRun(): boolean {
    return !!this.sqlText.trim() && !this.running;
  }

  // ------------------------------------------------------------
  // Schema explorer
  // ------------------------------------------------------------

  loadCatalogs(): void {
    this.explorerLoading = true;
    this.explorerError = '';

    this.configService.get('/query/trino/explorer/').subscribe({
      next: (response: { catalogs: string[] }) => {
        this.explorerLoading = false;
        this.catalogs = (response.catalogs || []).map(name => this.makeNode('catalog', name));
      },
      error: (error) => {
        this.explorerLoading = false;
        this.explorerError = error?.error?.error || 'Failed to load catalogs.';
      }
    });
  }

  private makeNode(type: ExplorerNode['type'], name: string, catalog?: string, schema?: string): ExplorerNode {
    return { type, name, catalog, schema, expanded: false, loading: false, loaded: false, children: [] };
  }

  toggleNode(node: ExplorerNode): void {
    if (node.type === 'table') {
      this.insertTableQuery(node);
      return;
    }

    node.expanded = !node.expanded;

    if (node.expanded && !node.loaded) {
      this.loadChildren(node);
    }
  }

  private loadChildren(node: ExplorerNode): void {
    node.loading = true;
    node.error = undefined;

    const params = node.type === 'catalog'
      ? { catalog: node.name }
      : { catalog: node.catalog, schema: node.name };

    const query = Object.entries(params)
      .map(([key, value]) => `${key}=${encodeURIComponent(value as string)}`)
      .join('&');

    this.configService.get(`/query/trino/explorer/?${query}`).subscribe({
      next: (response: { schemas?: string[]; tables?: string[] }) => {
        node.loading = false;
        node.loaded = true;

        if (node.type === 'catalog') {
          node.children = (response.schemas || []).map(name => this.makeNode('schema', name, node.name));
        } else {
          node.children = (response.tables || []).map(name => this.makeNode('table', name, node.catalog, node.name));
        }
      },
      error: (error) => {
        node.loading = false;
        node.error = error?.error?.error || 'Failed to load.';
      }
    });
  }

  private insertTableQuery(node: ExplorerNode): void {
    const fqName = `${node.catalog}.${node.schema}.${node.name}`;
    this.sqlText = `SELECT * FROM ${fqName} LIMIT 100;`;
  }

  // ------------------------------------------------------------
  // Editor / execution
  // ------------------------------------------------------------

  loadHistory(): void {
    this.configService.get('/query/history/?source=trino').subscribe({
      next: (response: QueryHistoryItem[]) => {
        this.history = Array.isArray(response) ? response.slice(0, 10) : [];
      },
      error: (error) => {
        console.error('Failed to load Trino query history', error);
      }
    });
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

    this.configService.post('/query/execute-trino/', {
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
