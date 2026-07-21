import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DialogModule } from 'primeng/dialog';
import { DropdownModule } from 'primeng/dropdown';
import { InputNumberModule } from 'primeng/inputnumber';
import { InputTextModule } from 'primeng/inputtext';

import { ConfigService } from '../../services/config.service';

export interface DataSource {
  id: number;
  name: string;
  endpoint: string;
  username: string;
  password: string;
  created_at: string;
  updated_at: string;
}

export interface DataDestination {
  id: number;
  name: string;
  endpoint: string;
  username: string;
  password: string;
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
    InputNumberModule
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

  ngOnInit(): void {
    this.loadIngestionPipelines();
    this.loadDataSources();
    this.loadDataDestinations();
  }

  /**
   * Load pipelines
   */
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

  /**
   * Load Data Sources
   */
  loadDataSources(): void {
    this.configService.get('/data-sources/').subscribe({
      next: (response: DataSource[]) => {
        this.dataSources = response;
      },
      error: (error) => {
        console.error('Failed to load data sources', error);
      }
    });
  }

  /**
   * Load Data Destinations
   */
  loadDataDestinations(): void {
    this.configService.get('/data-destination/').subscribe({
      next: (response: DataDestination[]) => {
        this.dataDestinations = response;
      },
      error: (error) => {
        console.error('Failed to load data destinations', error);
      }
    });
  }

  /**
   * Avatar initials
   */
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

  /**
   * Open Add Dialog
   */
  openNewPipelineDialog(): void {

    this.isEdit = false;

    this.selectedPipeline = null;

    this.newPipeline = {
      name: '',
      source: null,
      destination: null,
      sync_interval: 1
    };

    this.displayDialog = true;
  }

  /**
   * Open Edit Dialog
   */
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

  /**
   * Save Pipeline
   */
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

      this.configService.put(
        `/ingestion-pipelines/${this.selectedPipeline.id}/`,
        payload
      ).subscribe({

        next: () => {

          this.displayDialog = false;

          this.loadIngestionPipelines();

        },

        error: (error) => {

          console.error(error);

        }

      });

    } else {

      this.configService.post(
        '/ingestion-pipelines/',
        payload
      ).subscribe({

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

  /**
   * Delete Confirmation
   */
  confirmDelete(pipeline: IngestionPipeline): void {

    this.selectedPipeline = pipeline;

    this.deleteDialog = true;

  }

  /**
   * Delete Pipeline
   */
  deletePipeline(): void {

    if (!this.selectedPipeline) {
      return;
    }

    this.configService.delete(
      `/ingestion-pipelines/${this.selectedPipeline.id}/`
    ).subscribe({

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

  /**
   * Close Dialog
   */
  closeDialog(): void {

    this.displayDialog = false;

    this.selectedPipeline = null;

  }

  /**
   * Close Delete Dialog
   */
  /**
 * Sync pipeline now
 */
syncNow(pipeline: IngestionPipeline): void {
  this.configService.post(`/ingestion-pipelines/${pipeline.id}/run/`, {}).subscribe({
    next: () => {
      console.log(`Pipeline "${pipeline.name}" synced successfully.`);
      this.loadIngestionPipelines();
    },
    error: (error) => {
      console.error('Failed to sync pipeline', error);
    }
  });
}
  closeDeleteDialog(): void {

    this.deleteDialog = false;

    this.selectedPipeline = null;

  }

}