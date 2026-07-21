import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { DropdownModule } from 'primeng/dropdown';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ConfigService } from '../../services/config.service';

export interface DataSourceConfiguration {
  endpoint?: string;
  username?: string;
  password?: string;
  bucket?: string;
  folder?: string;
  region?: string;
}

export interface DataSource {
  id: number;
  name: string;
  source_type: string;
  configuration: DataSourceConfiguration;
  description?: string;
  is_active?: boolean;
  created_at: string;
  updated_at: string;
}

export interface SourceTypeOption {
  value: string;
  label: string;
}

export interface AssetItem {
  name: string;
  type: string;
  size: number;
  last_modified?: string;
}

@Component({
  selector: 'app-data-sources',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CardModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    DropdownModule,
    TableModule,
    TagModule,
    ProgressSpinnerModule
  ],
  templateUrl: './data-sources.component.html',
  styleUrl: './data-sources.component.css'
})
export class DataSourcesComponent implements OnInit {
  constructor(private configService: ConfigService) {}

  dataSources: DataSource[] = [];
  sourceTypes: SourceTypeOption[] = [];

  displayDialog = false;
  deleteDialog = false;
  configDialog = false;

  isEdit = false;
  selectedSource: DataSource | null = null;

  newSource: {
    name: string;
    source_type: string;
    description: string;
    is_active: boolean;
    configuration: DataSourceConfiguration;
  } = {
    name: '',
    source_type: '',
    description: '',
    is_active: true,
    configuration: {
      endpoint: '',
      username: '',
      password: '',
      bucket: '',
      folder: '',
      region: ''
    }
  };

  configModel: {
    source_type: string;
    bucket: string;
    folder: string;
    region: string;
  } = {
    source_type: '',
    bucket: '',
    folder: '',
    region: ''
  };

  connectionStatus = '';
  connectionError = '';

  availableBuckets: string[] = [];
  selectedBucket = '';
  assets: AssetItem[] = [];

  loadingSources = false;
  savingSource = false;
  deletingSource = false;

  loadingConnection = false;
  loadingBuckets = false;
  loadingAssets = false;
  savingConfiguration = false;

  ngOnInit(): void {
    this.loadDataSources();
    this.loadSourceTypes();
  }

  loadDataSources(): void {
    this.loadingSources = true;

    this.configService.get('/data-sources/').subscribe({
      next: (response: DataSource[]) => {
        this.dataSources = Array.isArray(response)
          ? response.map(source => ({
              ...source,
              configuration: source.configuration || {}
            }))
          : [];
        this.loadingSources = false;
      },
      error: (error) => {
        console.error('Failed to load data sources', error);
        this.loadingSources = false;
      }
    });
  }

  loadSourceTypes(): void {
    this.configService.get('/data-sources/source-types/').subscribe({
      next: (response: SourceTypeOption[]) => {
        this.sourceTypes = response;
      },
      error: (error) => {
        console.error('Failed to load source types', error);
      }
    });
  }

  getShortName(name: string): string {
    if (!name) {
      return '';
    }

    return name
      .split(' ')
      .map(word => word.charAt(0))
      .join('')
      .substring(0, 3)
      .toUpperCase();
  }

  getConnectionSeverity(): 'success' | 'danger' | 'warning' | 'info' | undefined {
    if (this.connectionStatus === 'Connected') {
      return 'success';
    }

    if (this.connectionStatus === 'Disconnected' || this.connectionStatus === 'Failed') {
      return 'danger';
    }

    if (this.connectionStatus === 'Checking...') {
      return 'warning';
    }

    return 'info';
  }

  formatBytes(bytes: number | null | undefined): string {
    if (bytes === null || bytes === undefined) {
      return '-';
    }

    if (bytes === 0) {
      return '0 Bytes';
    }

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  }

  getConfigValue(source: DataSource | null | undefined, key: keyof DataSourceConfiguration): string {
    return source?.configuration?.[key] || '';
  }

  resetNewSource(): void {
    this.newSource = {
      name: '',
      source_type: '',
      description: '',
      is_active: true,
      configuration: {
        endpoint: '',
        username: '',
        password: '',
        bucket: '',
        folder: '',
        region: ''
      }
    };
  }

  resetConfigurationState(): void {
    this.connectionStatus = '';
    this.connectionError = '';
    this.availableBuckets = [];
    this.selectedBucket = '';
    this.assets = [];

    this.configModel = {
      source_type: this.selectedSource?.source_type || '',
      bucket: this.selectedSource?.configuration?.bucket || '',
      folder: this.selectedSource?.configuration?.folder || '',
      region: this.selectedSource?.configuration?.region || ''
    };

    this.selectedBucket = this.selectedSource?.configuration?.bucket || '';
  }

  openNewSourceDialog(): void {
    this.isEdit = false;
    this.selectedSource = null;
    this.resetNewSource();
    this.displayDialog = true;
  }

  editSource(source: DataSource): void {
    this.isEdit = true;
    this.selectedSource = source;

    this.newSource = {
      name: source.name,
      source_type: source.source_type || '',
      description: source.description || '',
      is_active: source.is_active ?? true,
      configuration: {
        endpoint: source.configuration?.endpoint || '',
        username: source.configuration?.username || '',
        password: source.configuration?.password || '',
        bucket: source.configuration?.bucket || '',
        folder: source.configuration?.folder || '',
        region: source.configuration?.region || ''
      }
    };

    this.displayDialog = true;
  }

  saveSource(): void {
    if (
      !this.newSource.name.trim() ||
      !this.newSource.source_type.trim() ||
      !this.newSource.configuration.endpoint?.trim() ||
      !this.newSource.configuration.username?.trim() ||
      !this.newSource.configuration.password?.trim()
    ) {
      alert('Please fill all required fields.');
      return;
    }

    const payload = {
      name: this.newSource.name.trim(),
      source_type: this.newSource.source_type,
      description: this.newSource.description?.trim() || '',
      is_active: this.newSource.is_active,
      configuration: {
        endpoint: this.newSource.configuration.endpoint?.trim() || '',
        username: this.newSource.configuration.username?.trim() || '',
        password: this.newSource.configuration.password || '',
        bucket: this.newSource.configuration.bucket?.trim() || '',
        folder: this.newSource.configuration.folder?.trim() || '',
        region: this.newSource.configuration.region?.trim() || ''
      }
    };

    this.savingSource = true;

    if (this.isEdit && this.selectedSource) {
      this.configService.put(`/data-sources/${this.selectedSource.id}/`, payload).subscribe({
        next: () => {
          this.savingSource = false;
          this.displayDialog = false;
          this.selectedSource = null;
          this.loadDataSources();
        },
        error: (error) => {
          console.error('Failed to update data source', error);
          this.savingSource = false;
        }
      });
    } else {
      this.configService.post('/data-sources/', payload).subscribe({
        next: () => {
          this.savingSource = false;
          this.displayDialog = false;
          this.loadDataSources();
        },
        error: (error) => {
          console.error('Failed to create data source', error);
          this.savingSource = false;
        }
      });
    }
  }

  confirmDelete(source: DataSource): void {
    this.selectedSource = source;
    this.deleteDialog = true;
  }

  deleteSource(): void {
    if (!this.selectedSource) {
      return;
    }

    this.deletingSource = true;

    this.configService.delete(`/data-sources/${this.selectedSource.id}/`).subscribe({
      next: () => {
        this.deletingSource = false;
        this.deleteDialog = false;
        this.selectedSource = null;
        this.loadDataSources();
      },
      error: (error) => {
        console.error('Failed to delete data source', error);
        this.deletingSource = false;
      }
    });
  }

  closeDialog(): void {
    this.displayDialog = false;
    this.selectedSource = null;
    this.resetNewSource();
  }

  closeDeleteDialog(): void {
    this.deleteDialog = false;
    this.selectedSource = null;
  }

  configure(source: DataSource): void {
    this.selectedSource = source;
    this.resetConfigurationState();
    this.configDialog = true;
    this.checkConnection(source);
  }

  closeConfigDialog(): void {
    this.configDialog = false;
    this.selectedSource = null;
    this.resetConfigurationState();
  }

  checkConnection(source?: DataSource): void {
    const target = source || this.selectedSource;

    if (!target) {
      return;
    }

    this.loadingConnection = true;
    this.connectionStatus = 'Checking...';
    this.connectionError = '';

    this.configService.get(`/data-sources/${target.id}/check-connection/`).subscribe({
      next: (response: any) => {
        this.loadingConnection = false;
        this.connectionStatus = response?.connected ? 'Connected' : 'Disconnected';
        this.connectionError = response?.error || '';
        this.availableBuckets = Array.isArray(response?.buckets) ? response.buckets : [];

        if (this.configModel.bucket && this.availableBuckets.includes(this.configModel.bucket)) {
          this.selectedBucket = this.configModel.bucket;
        } else if (this.availableBuckets.length > 0) {
          this.selectedBucket = this.availableBuckets[0];
        } else {
          this.selectedBucket = '';
        }

        if (this.selectedBucket) {
          this.configModel.bucket = this.selectedBucket;
          this.loadAssets();
        }
      },
      error: (error) => {
        console.error('Connection check failed', error);
        this.loadingConnection = false;
        this.connectionStatus = 'Failed';
        this.connectionError = error?.error?.error || 'Unable to connect.';
        this.availableBuckets = [];
        this.assets = [];
      }
    });
  }

  loadBuckets(source?: DataSource): void {
    const target = source || this.selectedSource;

    if (!target) {
      return;
    }

    this.loadingBuckets = true;

    this.configService.get(`/data-sources/${target.id}/list-buckets/`).subscribe({
      next: (response: any) => {
        this.loadingBuckets = false;
        this.availableBuckets = Array.isArray(response) ? response : [];
      },
      error: (error) => {
        console.error('Failed to load buckets', error);
        this.loadingBuckets = false;
        this.availableBuckets = [];
      }
    });
  }

  onBucketChange(): void {
    this.configModel.bucket = this.selectedBucket;
    this.loadAssets();
  }

  loadAssets(source?: DataSource): void {
    const target = source || this.selectedSource;

    if (!target || !this.selectedBucket) {
      this.assets = [];
      return;
    }

    this.loadingAssets = true;

    this.configService
      .get(`/data-sources/${target.id}/list-assets/?bucket=${encodeURIComponent(this.selectedBucket)}`)
      .subscribe({
        next: (response: AssetItem[]) => {
          this.loadingAssets = false;
          this.assets = Array.isArray(response) ? response : [];
        },
        error: (error) => {
          console.error('Failed to load assets', error);
          this.loadingAssets = false;
          this.assets = [];
        }
      });
  }

  saveConfiguration(): void {
    if (!this.selectedSource) {
      return;
    }

    const payload = {
      name: this.selectedSource.name,
      source_type: this.configModel.source_type || this.selectedSource.source_type,
      description: this.selectedSource.description || '',
      is_active: this.selectedSource.is_active ?? true,
      configuration: {
        ...(this.selectedSource.configuration || {}),
        bucket: this.selectedBucket || '',
        folder: this.configModel.folder?.trim() || '',
        region: this.configModel.region?.trim() || ''
      }
    };

    this.savingConfiguration = true;

    this.configService.put(`/data-sources/${this.selectedSource.id}/`, payload).subscribe({
      next: () => {
        this.savingConfiguration = false;
        this.configDialog = false;
        this.selectedSource = null;
        this.loadDataSources();
      },
      error: (error) => {
        console.error('Failed to save configuration', error);
        this.savingConfiguration = false;
      }
    });
  }
}