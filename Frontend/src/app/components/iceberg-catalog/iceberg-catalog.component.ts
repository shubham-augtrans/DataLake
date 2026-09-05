import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TagModule } from 'primeng/tag';

import { ConfigService } from '../../services/config.service';

export interface TableColumn {
  name: string;
  type: string;
  required: boolean;
}

export interface TableDetail {
  namespace: string;
  table: string;
  location: string;
  columns: TableColumn[];
  snapshot_count: number;
  current_snapshot_id: number | null;
  total_records: string | null;
  total_data_files: string | null;
  last_updated_ms: number | null;
}

@Component({
  selector: 'app-iceberg-catalog',
  standalone: true,
  imports: [CommonModule, ButtonModule, ProgressSpinnerModule, TagModule],
  templateUrl: './iceberg-catalog.component.html',
  styleUrl: './iceberg-catalog.component.css'
})
export class IcebergCatalogComponent implements OnInit {

  constructor(private configService: ConfigService) {}

  loadingNamespaces = false;
  loadingTables = false;
  loadingDetail = false;

  namespaces: string[] = [];
  selectedNamespace: string | null = null;

  tables: string[] = [];
  selectedTable: string | null = null;

  tableDetail: TableDetail | null = null;

  errorMessage = '';

  ngOnInit(): void {
    this.loadNamespaces();
  }

  loadNamespaces(): void {
    this.loadingNamespaces = true;
    this.errorMessage = '';

    this.configService.get('/catalog/namespaces/').subscribe({
      next: (response: { namespaces: string[] }) => {
        this.loadingNamespaces = false;
        this.namespaces = response?.namespaces || [];

        if (this.namespaces.length > 0) {
          this.selectNamespace(this.namespaces[0]);
        }
      },
      error: (error) => {
        this.loadingNamespaces = false;
        this.errorMessage = error?.error?.error || 'Failed to reach the Iceberg REST catalog.';
      }
    });
  }

  selectNamespace(namespace: string): void {
    this.selectedNamespace = namespace;
    this.selectedTable = null;
    this.tableDetail = null;
    this.tables = [];
    this.loadingTables = true;
    this.errorMessage = '';

    this.configService.get(`/catalog/tables/?namespace=${encodeURIComponent(namespace)}`).subscribe({
      next: (response: { tables: string[] }) => {
        this.loadingTables = false;
        this.tables = response?.tables || [];

        if (this.tables.length > 0) {
          this.selectTable(this.tables[0]);
        }
      },
      error: (error) => {
        this.loadingTables = false;
        this.errorMessage = error?.error?.error || 'Failed to list tables for this namespace.';
      }
    });
  }

  selectTable(table: string): void {
    if (!this.selectedNamespace) {
      return;
    }

    this.selectedTable = table;
    this.tableDetail = null;
    this.loadingDetail = true;
    this.errorMessage = '';

    this.configService
      .get(`/catalog/tables/detail/?namespace=${encodeURIComponent(this.selectedNamespace)}&table=${encodeURIComponent(table)}`)
      .subscribe({
        next: (response: TableDetail) => {
          this.loadingDetail = false;
          this.tableDetail = response;
        },
        error: (error) => {
          this.loadingDetail = false;
          this.errorMessage = error?.error?.error || 'Failed to load table schema.';
        }
      });
  }

  refresh(): void {
    this.loadNamespaces();
  }
}
