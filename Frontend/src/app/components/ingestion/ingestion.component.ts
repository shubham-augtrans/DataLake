import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DialogModule } from 'primeng/dialog';
import { DropdownModule } from 'primeng/dropdown';
import { InputNumberModule } from 'primeng/inputnumber';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { RadioButtonModule } from 'primeng/radiobutton';
import { StepperModule } from 'primeng/stepper';
import { TagModule } from 'primeng/tag';

import { Observable, of } from 'rxjs';
import { map } from 'rxjs/operators';

import { ConfigService } from '../../services/config.service';

export interface DataSourceConfig {
  host?: string;
  port?: string;
  database?: string;
  username?: string;
  password?: string;
  authSource?: string;
  table?: string;
  collection?: string;
  topic?: string;
  folder_url?: string;
}

export interface DataSource {
  id: number;
  name: string;
  source_type: string;
  configuration: DataSourceConfig;
  created_at: string;
  updated_at: string;
}

export interface DataDestinationConfig {
  endpoint?: string;
  access_key?: string;
  secret_key?: string;
  bucket?: string;
}

export interface DataDestination {
  id: number;
  name: string;
  destination_type: string;
  configuration: DataDestinationConfig;
  created_at: string;
  updated_at: string;
}

export interface IngestionPipeline {
  id: number;
  name: string;
  source: number;
  source_name: string;
  destination: number;
  destination_name: string;
  sync_interval: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectorOption {
  key: string;
  label: string;
  icon: string;
  description: string;
  enabled: boolean;
}

@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CardModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    DropdownModule,
    InputNumberModule,
    PasswordModule,
    RadioButtonModule,
    StepperModule,
    TagModule
  ],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.css'
})
export class IngestionComponent implements OnInit {

  constructor(private configService: ConfigService) {}

  ingestionPipelines: IngestionPipeline[] = [];
  dataSources: DataSource[] = [];
  dataDestinations: DataDestination[] = [];

  displayDialog = false;
  deleteDialog = false;
  isEdit = false;
  selectedPipeline: IngestionPipeline | null = null;

  newPipeline = {
    name: '',
    source: null as number | null,
    destination: null as number | null,
    sync_interval: 1
  };

  /* ===========================
     "Add data" connector grid
  =========================== */

  connectors: ConnectorOption[] = [
    { key: 'postgres', label: 'PostgreSQL', icon: 'database', description: 'Ingest tables from a PostgreSQL database.', enabled: true },
    { key: 'mongo', label: 'MongoDB', icon: 'data_object', description: 'Ingest collections from a MongoDB database.', enabled: true },
    { key: 'kafka', label: 'Kafka', icon: 'sync_alt', description: 'Stream events from Kafka topics.', enabled: true },
    { key: 'google_drive', label: 'Google Drive', icon: 'drive_folder_upload', description: 'Ingest a CSV file or Google Sheet from a public Drive folder.', enabled: true },
    { key: 'mysql', label: 'MySQL', icon: 'storage', description: 'Ingest tables from a MySQL database.', enabled: false },
    { key: 'sqlserver', label: 'SQL Server', icon: 'dns', description: 'Ingest tables from a SQL Server database.', enabled: false }
  ];

  /* ===========================
     Wizard state
  =========================== */

  wizardVisible = false;
  wizardStep = 0;
  wizardSaving = false;
  wizardError = '';
  selectedConnector: ConnectorOption | null = null;

  connectionMode: 'new' | 'existing' = 'new';
  existingSourceId: number | null = null;
  sourceForm = {
    name: '',
    host: '',
    port: '',
    database: '',
    username: '',
    password: '',
    authSource: 'admin',
    folder_url: ''
  };

  pipelineName = '';

  sourceDetails = {
    table: '',
    database: '',
    collection: '',
    topic: '',
    filename: ''
  };

  destinationMode: 'new' | 'existing' = 'existing';
  existingDestinationId: number | null = null;
  destinationForm = {
    name: '',
    endpoint: '',
    access_key: '',
    secret_key: '',
    bucket: ''
  };

  syncInterval = 1;

  ngOnInit(): void {
    this.loadIngestionPipelines();
    this.loadDataSources();
    this.loadDataDestinations();
  }

  loadIngestionPipelines(): void {
    this.configService.get('/ingestion-pipelines/').subscribe({
      next: (response: IngestionPipeline[]) => {
        this.ingestionPipelines = response;
      },
      error: (error) => {
        console.error('Failed to load ingestion pipelines', error);
      }
    });
  }

  loadDataSources(): void {
    this.configService.get('/data-sources/').subscribe({
      next: (response: DataSource[]) => {
        this.dataSources = Array.isArray(response)
          ? response.map(source => ({ ...source, configuration: source.configuration || {} }))
          : [];
      },
      error: (error) => {
        console.error('Failed to load data sources', error);
      }
    });
  }

  loadDataDestinations(): void {
    this.configService.get('/data-destination/').subscribe({
      next: (response: DataDestination[]) => {
        this.dataDestinations = Array.isArray(response)
          ? response.map(dest => ({ ...dest, configuration: dest.configuration || {} }))
          : [];
      },
      error: (error) => {
        console.error('Failed to load data destinations', error);
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

  private defaultPortFor(connectorKey: string): string {
    switch (connectorKey) {
      case 'postgres':
        return '5432';
      case 'mongo':
        return '27017';
      case 'kafka':
        return '9094';
      default:
        return '';
    }
  }

  /* ===========================
     Wizard: existing records filtered by type
  =========================== */

  get existingSourcesForConnector(): DataSource[] {
    if (!this.selectedConnector) {
      return [];
    }
    return this.dataSources.filter(s => s.source_type === this.selectedConnector!.key);
  }

  get minioDestinations(): DataDestination[] {
    return this.dataDestinations.filter(d => d.destination_type === 'minio');
  }

  /* ===========================
     Wizard: open / close
  =========================== */

  openWizard(connector: ConnectorOption): void {
    if (!connector.enabled) {
      return;
    }

    this.selectedConnector = connector;
    this.wizardStep = 0;
    this.wizardError = '';
    this.wizardSaving = false;

    this.connectionMode = 'new';
    this.existingSourceId = null;
    this.sourceForm = {
      name: '',
      host: '',
      port: this.defaultPortFor(connector.key),
      database: '',
      username: '',
      password: '',
      authSource: 'admin',
      folder_url: ''
    };

    this.pipelineName = '';
    this.sourceDetails = { table: '', database: '', collection: '', topic: '', filename: '' };

    const hasMinioDestination = this.minioDestinations.length > 0;
    this.destinationMode = hasMinioDestination ? 'existing' : 'new';
    this.existingDestinationId = hasMinioDestination ? this.minioDestinations[0].id : null;
    this.destinationForm = { name: '', endpoint: '', access_key: '', secret_key: '', bucket: '' };

    this.syncInterval = 1;

    this.wizardVisible = true;
  }

  closeWizard(): void {
    this.wizardVisible = false;
    this.selectedConnector = null;
    this.wizardError = '';
  }

  /* ===========================
     Wizard: step validation
  =========================== */

  get isConnectionStepValid(): boolean {
    if (this.connectionMode === 'existing') {
      return this.existingSourceId !== null;
    }

    if (!this.selectedConnector) {
      return false;
    }

    const f = this.sourceForm;

    if (this.selectedConnector.key === 'postgres') {
      return !!(f.name.trim() && f.host.trim() && f.port.trim() && f.database.trim() && f.username.trim() && f.password);
    }

    if (this.selectedConnector.key === 'mongo' || this.selectedConnector.key === 'kafka') {
      return !!(f.name.trim() && f.host.trim() && f.port.trim() && f.username.trim() && f.password);
    }

    if (this.selectedConnector.key === 'google_drive') {
      return !!(f.name.trim() && f.folder_url.trim());
    }

    return false;
  }

  get isIngestionSetupStepValid(): boolean {
    return !!this.pipelineName.trim();
  }

  get isSourceStepValid(): boolean {
    if (!this.selectedConnector) {
      return false;
    }

    if (this.selectedConnector.key === 'postgres') {
      return !!this.sourceDetails.table.trim();
    }

    if (this.selectedConnector.key === 'mongo') {
      return !!(this.sourceDetails.database.trim() && this.sourceDetails.collection.trim());
    }

    if (this.selectedConnector.key === 'kafka') {
      return !!this.sourceDetails.topic.trim();
    }

    if (this.selectedConnector.key === 'google_drive') {
      return !!this.sourceDetails.filename.trim();
    }

    return false;
  }

  get isDestinationStepValid(): boolean {
    if (this.destinationMode === 'existing') {
      return this.existingDestinationId !== null;
    }

    const f = this.destinationForm;
    return !!(f.name.trim() && f.endpoint.trim() && f.access_key.trim() && f.secret_key && f.bucket.trim());
  }

  get isScheduleStepValid(): boolean {
    return this.syncInterval >= 1 && this.syncInterval <= 24;
  }

  get sourceSummaryLabel(): string {
    if (this.connectionMode === 'existing') {
      const source = this.existingSourcesForConnector.find(s => s.id === this.existingSourceId);
      return source ? source.name : '—';
    }
    return this.sourceForm.name.trim() || '—';
  }

  get destinationSummaryLabel(): string {
    if (this.destinationMode === 'existing') {
      const destination = this.minioDestinations.find(d => d.id === this.existingDestinationId);
      return destination ? destination.name : '—';
    }
    return this.destinationForm.name.trim() || '—';
  }

  /* ===========================
     Wizard: create pipeline
  =========================== */

  private resolveSource(): Observable<number> {
    if (this.connectionMode === 'existing' && this.existingSourceId !== null) {
      return of(this.existingSourceId);
    }

    let configuration: DataSourceConfig;

    if (this.selectedConnector?.key === 'postgres') {
      configuration = {
        host: this.sourceForm.host.trim(),
        port: this.sourceForm.port.trim(),
        database: this.sourceForm.database.trim(),
        username: this.sourceForm.username.trim(),
        password: this.sourceForm.password,
        table: this.sourceDetails.table.trim()
      };
    } else if (this.selectedConnector?.key === 'kafka') {
      configuration = {
        host: this.sourceForm.host.trim(),
        port: this.sourceForm.port.trim(),
        username: this.sourceForm.username.trim(),
        password: this.sourceForm.password,
        topic: this.sourceDetails.topic.trim()
      };
    } else if (this.selectedConnector?.key === 'google_drive') {
      configuration = {
        folder_url: this.sourceForm.folder_url.trim()
      };
    } else {
      configuration = {
        host: this.sourceForm.host.trim(),
        port: this.sourceForm.port.trim(),
        username: this.sourceForm.username.trim(),
        password: this.sourceForm.password,
        authSource: this.sourceForm.authSource.trim() || 'admin',
        database: this.sourceDetails.database.trim(),
        collection: this.sourceDetails.collection.trim()
      };
    }

    const payload = {
      name: this.sourceForm.name.trim(),
      source_type: this.selectedConnector?.key,
      description: '',
      is_active: true,
      configuration
    };

    return this.configService.post('/data-sources/', payload).pipe(map((res: DataSource) => res.id));
  }

  private resolveDestination(): Observable<number> {
    if (this.destinationMode === 'existing' && this.existingDestinationId !== null) {
      return of(this.existingDestinationId);
    }

    const payload = {
      name: this.destinationForm.name.trim(),
      destination_type: 'minio',
      description: '',
      is_active: true,
      configuration: {
        endpoint: this.destinationForm.endpoint.trim(),
        access_key: this.destinationForm.access_key.trim(),
        secret_key: this.destinationForm.secret_key,
        bucket: this.destinationForm.bucket.trim()
      }
    };

    return this.configService.post('/data-destination/', payload).pipe(map((res: DataDestination) => res.id));
  }

  createPipeline(): void {
    this.wizardError = '';
    this.wizardSaving = true;

    this.resolveSource().subscribe({
      next: (sourceId) => {
        this.resolveDestination().subscribe({
          next: (destinationId) => {
            const sourceObject = this.selectedConnector?.key === 'postgres'
              ? this.sourceDetails.table.trim()
              : this.selectedConnector?.key === 'kafka'
                ? this.sourceDetails.topic.trim()
                : this.selectedConnector?.key === 'google_drive'
                  ? this.sourceDetails.filename.trim()
                  : this.sourceDetails.collection.trim();

            const payload = {
              name: this.pipelineName.trim(),
              source: sourceId,
              destination: destinationId,
              source_object: sourceObject,
              sync_interval: this.syncInterval
            };

            this.configService.post('/ingestion-pipelines/', payload).subscribe({
              next: () => {
                this.wizardSaving = false;
                this.closeWizard();
                this.loadIngestionPipelines();
                this.loadDataSources();
                this.loadDataDestinations();
              },
              error: (error) => {
                this.wizardSaving = false;
                this.wizardError = error?.error?.detail || 'Failed to create the ingestion pipeline.';
              }
            });
          },
          error: (error) => {
            this.wizardSaving = false;
            this.wizardError = error?.error?.configuration || 'Failed to prepare the destination.';
          }
        });
      },
      error: (error) => {
        this.wizardSaving = false;
        this.wizardError = error?.error?.configuration || 'Failed to prepare the data source.';
      }
    });
  }

  /* ===========================
     Existing pipeline management
  =========================== */

  editPipeline(pipeline: IngestionPipeline): void {
    this.isEdit = true;
    this.selectedPipeline = pipeline;

    this.newPipeline = {
      name: pipeline.name,
      source: pipeline.source,
      destination: pipeline.destination,
      sync_interval: pipeline.sync_interval
    };

    this.displayDialog = true;
  }

  savePipeline(): void {
    if (
      !this.newPipeline.name ||
      this.newPipeline.source === null ||
      this.newPipeline.destination === null ||
      this.newPipeline.sync_interval === null
    ) {
      alert('Please fill all fields.');
      return;
    }

    const payload = {
      name: this.newPipeline.name,
      source: this.newPipeline.source,
      destination: this.newPipeline.destination,
      sync_interval: this.newPipeline.sync_interval
    };

    if (this.isEdit && this.selectedPipeline) {
      this.configService.put(`/ingestion-pipelines/${this.selectedPipeline.id}/`, payload).subscribe({
        next: () => {
          this.displayDialog = false;
          this.loadIngestionPipelines();
        },
        error: (error) => {
          console.error(error);
        }
      });
    }
  }

  confirmDelete(pipeline: IngestionPipeline): void {
    this.selectedPipeline = pipeline;
    this.deleteDialog = true;
  }

  deletePipeline(): void {
    if (!this.selectedPipeline) {
      return;
    }

    this.configService.delete(`/ingestion-pipelines/${this.selectedPipeline.id}/`).subscribe({
      next: () => {
        this.deleteDialog = false;
        this.selectedPipeline = null;
        this.loadIngestionPipelines();
      },
      error: (error) => {
        console.error(error);
      }
    });
  }

  closeDialog(): void {
    this.displayDialog = false;
    this.selectedPipeline = null;
  }

  closeDeleteDialog(): void {
    this.deleteDialog = false;
    this.selectedPipeline = null;
  }

  syncNow(pipeline: IngestionPipeline): void {
    this.configService.post(`/ingestion-pipelines/${pipeline.id}/run/`, {}).subscribe({
      next: () => {
        this.loadIngestionPipelines();
      },
      error: (error) => {
        console.error('Failed to sync pipeline', error);
      }
    });
  }
}
