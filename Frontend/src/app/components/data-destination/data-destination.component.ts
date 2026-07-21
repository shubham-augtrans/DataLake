import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { DropdownModule } from 'primeng/dropdown';

import { ConfigService } from '../../services/config.service';

export interface DestinationTypeOption {
  value: string;
  label: string;
}

export interface DataDestinationConfiguration {
  host?: string;
  port?: string;
  database?: string;
  username?: string;
  password?: string;
  service_name?: string;
  account?: string;
  warehouse?: string;
  schema?: string;
  path?: string;
  endpoint?: string;
  access_key?: string;
  secret_key?: string;
  region?: string;
  bucket?: string;
  account_name?: string;
  container?: string;
  connection_string?: string;
}

export interface DataDestination {
  id: number;
  name: string;
  destination_type: string;
  configuration: DataDestinationConfiguration;
  description?: string;
  is_active?: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConfigField {
  key: keyof DataDestinationConfiguration;
  label: string;
  type?: string;
  placeholder?: string;
}

export interface NotebookResponse {
  name: string;
  url: string;
}

@Component({
  selector: 'app-data-destination',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CardModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    DropdownModule
  ],
  templateUrl: './data-destination.component.html',
  styleUrl: './data-destination.component.css'
})
export class DataDestinationComponent implements OnInit {
  constructor(private configService: ConfigService) {}

  dataDestinations: DataDestination[] = [];
  destinationTypes: DestinationTypeOption[] = [];
  visibleConfigFields: ConfigField[] = [];

  displayDialog = false;
  deleteDialog = false;
  isEdit = false;

  selectedDestination: DataDestination | null = null;

  jupyterLoadingId: number | null = null;

  newDestination: {
    name: string;
    destination_type: string;
    description: string;
    is_active: boolean;
    configuration: DataDestinationConfiguration;
  } = this.getEmptyDestinationModel();

  ngOnInit(): void {
    this.loadDataDestinations();
    this.loadDestinationTypes();
  }

  getEmptyDestinationModel() {
    return {
      name: '',
      destination_type: '',
      description: '',
      is_active: true,
      configuration: {}
    };
  }

  loadDataDestinations(): void {
    this.configService.get('/data-destination/').subscribe({
      next: (response: DataDestination[]) => {
        this.dataDestinations = Array.isArray(response)
          ? response.map(item => ({
              ...item,
              configuration: item.configuration || {}
            }))
          : [];
      },
      error: (error) => {
        console.error('Failed to load data destinations', error);
      }
    });
  }

  loadDestinationTypes(): void {
    this.configService.get('/data-destination/destination-types/').subscribe({
      next: (response: DestinationTypeOption[]) => {
        this.destinationTypes = Array.isArray(response) ? response : [];
      },
      error: (error) => {
        console.error('Failed to load destination types', error);
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

  getConfigValue(
    destination: DataDestination | null | undefined,
    key: keyof DataDestinationConfiguration
  ): string {
    const value = destination?.configuration?.[key];
    return value !== undefined && value !== null ? String(value) : '';
  }

  getConfigFieldsByType(type: string): ConfigField[] {
    const fieldMap: Record<string, ConfigField[]> = {
      postgresql: [
        { key: 'host', label: 'Host', placeholder: 'localhost' },
        { key: 'port', label: 'Port', placeholder: '5432' },
        { key: 'database', label: 'Database', placeholder: 'mydb' },
        { key: 'username', label: 'Username', placeholder: 'postgres' },
        { key: 'password', label: 'Password', type: 'password', placeholder: 'Enter password' }
      ],
      mysql: [
        { key: 'host', label: 'Host', placeholder: 'localhost' },
        { key: 'port', label: 'Port', placeholder: '3306' },
        { key: 'database', label: 'Database', placeholder: 'mydb' },
        { key: 'username', label: 'Username', placeholder: 'root' },
        { key: 'password', label: 'Password', type: 'password', placeholder: 'Enter password' }
      ],
      mongo: [
        { key: 'host', label: 'Host', placeholder: 'localhost' },
        { key: 'port', label: 'Port', placeholder: '27017' },
        { key: 'database', label: 'Database', placeholder: 'mydb' },
        { key: 'username', label: 'Username', placeholder: 'mongo-user' },
        { key: 'password', label: 'Password', type: 'password', placeholder: 'Enter password' }
      ],
      sqlserver: [
        { key: 'host', label: 'Host', placeholder: 'localhost' },
        { key: 'port', label: 'Port', placeholder: '1433' },
        { key: 'database', label: 'Database', placeholder: 'mydb' },
        { key: 'username', label: 'Username', placeholder: 'sa' },
        { key: 'password', label: 'Password', type: 'password', placeholder: 'Enter password' }
      ],
      oracle: [
        { key: 'host', label: 'Host', placeholder: 'localhost' },
        { key: 'port', label: 'Port', placeholder: '1521' },
        { key: 'service_name', label: 'Service Name', placeholder: 'ORCL' },
        { key: 'username', label: 'Username', placeholder: 'system' },
        { key: 'password', label: 'Password', type: 'password', placeholder: 'Enter password' }
      ],
      snowflake: [
        { key: 'account', label: 'Account', placeholder: 'account-id' },
        { key: 'warehouse', label: 'Warehouse', placeholder: 'COMPUTE_WH' },
        { key: 'database', label: 'Database', placeholder: 'MY_DB' },
        { key: 'schema', label: 'Schema', placeholder: 'PUBLIC' },
        { key: 'username', label: 'Username', placeholder: 'user' },
        { key: 'password', label: 'Password', type: 'password', placeholder: 'Enter password' }
      ],
      delta_lake: [
        { key: 'path', label: 'Path', placeholder: '/data/delta/table' }
      ],
      minio: [
        { key: 'endpoint', label: 'Endpoint', placeholder: 'http://localhost:9000' },
        { key: 'access_key', label: 'Access Key', placeholder: 'minioadmin' },
        { key: 'secret_key', label: 'Secret Key', type: 'password', placeholder: 'Enter secret key' }
      ],
      aws_s3: [
        { key: 'region', label: 'Region', placeholder: 'ap-south-1' },
        { key: 'bucket', label: 'Bucket', placeholder: 'my-bucket' },
        { key: 'access_key', label: 'Access Key', placeholder: 'AKIA...' },
        { key: 'secret_key', label: 'Secret Key', type: 'password', placeholder: 'Enter secret key' }
      ],
      azure_blob: [
        { key: 'account_name', label: 'Account Name', placeholder: 'storageaccount' },
        { key: 'container', label: 'Container', placeholder: 'container-name' },
        { key: 'connection_string', label: 'Connection String', type: 'password', placeholder: 'Enter connection string' }
      ]
    };

    return fieldMap[type] || [];
  }

  getNewConfigValue(key: keyof DataDestinationConfiguration): string {
    const value = this.newDestination.configuration?.[key];
    return value !== undefined && value !== null ? String(value) : '';
  }

  setNewConfigValue(key: keyof DataDestinationConfiguration, value: string): void {
    this.newDestination.configuration = {
      ...this.newDestination.configuration,
      [key]: value
    };
  }

  trackByFieldKey(index: number, field: ConfigField): string {
    return String(field.key);
  }

  openNewSourceDialog(): void {
    this.isEdit = false;
    this.selectedDestination = null;
    this.newDestination = this.getEmptyDestinationModel();
    this.visibleConfigFields = [];
    this.displayDialog = true;
  }

  editSource(destination: DataDestination): void {
    this.isEdit = true;
    this.selectedDestination = destination;

    this.newDestination = {
      name: destination.name,
      destination_type: destination.destination_type || '',
      description: destination.description || '',
      is_active: destination.is_active ?? true,
      configuration: { ...(destination.configuration || {}) }
    };

    this.visibleConfigFields = this.getConfigFieldsByType(this.newDestination.destination_type);
    this.displayDialog = true;
  }

  onDestinationTypeChange(): void {
    const currentType = this.newDestination.destination_type;
    const currentConfig = { ...(this.newDestination.configuration || {}) };
    const allowedFields = this.getConfigFieldsByType(currentType);

    const nextConfig: DataDestinationConfiguration = {};
    allowedFields.forEach((field) => {
      nextConfig[field.key] = currentConfig[field.key] || '';
    });

    this.newDestination.configuration = nextConfig;
    this.visibleConfigFields = allowedFields;
  }

  buildPayload() {
    const allowedKeys = this.visibleConfigFields.map(field => field.key);

    const configuration = allowedKeys.reduce((acc, key) => {
      const rawValue = this.newDestination.configuration?.[key];
      acc[key] = typeof rawValue === 'string' ? rawValue.trim() : rawValue || '';
      return acc;
    }, {} as Record<string, any>);

    return {
      name: this.newDestination.name.trim(),
      destination_type: this.newDestination.destination_type,
      description: this.newDestination.description.trim(),
      is_active: this.newDestination.is_active,
      configuration
    };
  }

  saveSource(): void {
    if (!this.newDestination.name.trim() || !this.newDestination.destination_type) {
      alert('Please fill required fields.');
      return;
    }

    const payload = this.buildPayload();

    if (this.isEdit && this.selectedDestination) {
      this.configService.put(
        `/data-destination/${this.selectedDestination.id}/`,
        payload
      ).subscribe({
        next: () => {
          this.displayDialog = false;
          this.selectedDestination = null;
          this.newDestination = this.getEmptyDestinationModel();
          this.visibleConfigFields = [];
          this.loadDataDestinations();
        },
        error: (error) => {
          console.error('Failed to update data destination', error);
          alert(error?.error?.configuration || 'Failed to update destination.');
        }
      });
    } else {
      this.configService.post(
        '/data-destination/',
        payload
      ).subscribe({
        next: () => {
          this.displayDialog = false;
          this.newDestination = this.getEmptyDestinationModel();
          this.visibleConfigFields = [];
          this.loadDataDestinations();
        },
        error: (error) => {
          console.error('Failed to create data destination', error);
          alert(error?.error?.configuration || 'Failed to create destination.');
        }
      });
    }
  }

  confirmDelete(destination: DataDestination): void {
    this.selectedDestination = destination;
    this.deleteDialog = true;
  }

  deleteSource(): void {
    if (!this.selectedDestination) {
      return;
    }

    this.configService.delete(`/data-destination/${this.selectedDestination.id}/`).subscribe({
      next: () => {
        this.deleteDialog = false;
        this.selectedDestination = null;
        this.loadDataDestinations();
      },
      error: (error) => {
        console.error('Failed to delete destination', error);
      }
    });
  }

  closeDialog(): void {
    this.displayDialog = false;
    this.selectedDestination = null;
    this.newDestination = this.getEmptyDestinationModel();
    this.visibleConfigFields = [];
  }

  closeDeleteDialog(): void {
    this.deleteDialog = false;
    this.selectedDestination = null;
  }

  openJupyterNotebook(destination: DataDestination): void {
    this.jupyterLoadingId = destination.id;

    this.configService.get(`/data-destination/${destination.id}/notebook/`).subscribe({
      next: (response: NotebookResponse) => {
        this.jupyterLoadingId = null;
        if (response?.url) {
          window.open(response.url, '_blank');
        } else {
          alert('No Jupyter URL returned for this destination.');
        }
      },
      error: (error) => {
        this.jupyterLoadingId = null;
        console.error('Failed to fetch Jupyter notebook URL', error);
        alert(error?.error?.detail || 'Failed to open Jupyter notebook.');
      }
    });
  }
}