import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { ProgressBarModule } from 'primeng/progressbar';
import { Router } from '@angular/router';

import { ConfigService } from '../../services/config.service';
import { environment } from '../../../environments/environment';

export interface IngestionPipelineSummary {
  id: number;
  nifi_process_group_id: string | null;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    CardModule,
    ButtonModule,
    ProgressBarModule
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {

  dataSourcesCount: number = 0;
  dataDestinationsCount: number = 0;
  pipelinesCount: number = 0;
  runningPipelinesCount: number = 0;

  activities = [
    {
      type: 'success',
      icon: 'terminal',
      title: 'Query executed successfully',
      time: '10:42 AM',
      description: "SELECT user_id, sum(revenue) FROM core.transactions WHERE date >= '2023-10-01' GROUP BY 1",
      tag: 'Cluster-A',
      statusText: 'Success'
    },
    {
      type: 'error',
      icon: 'error',
      title: "Job 'Nightly_ETL' failed",
      time: '03:15 AM',
      description: 'OutOfMemoryError: Java heap space during join operation',
      tag: 'Pipeline-04',
      statusText: 'Failed'
    },
    {
      type: 'info',
      icon: 'description',
      title: 'New Notebook Created',
      time: 'Yesterday',
      description: 'Customer_Segmentation_Q3_Analysis.ipynb',
      tag: 'Workspace/Marketing',
      statusText: 'Active'
    }
  ];

  constructor(
    private configService: ConfigService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadDataSources();
    this.loadDataDestinations();
    this.loadPipelines();
  }

  loadDataSources(): void {
    this.configService.get('/data-sources/count').subscribe({
      next: (response: { count: number }) => {
        this.dataSourcesCount = response?.count || 0;
      },
      error: (error) => {
        console.error('Failed to load data sources:', error);
        this.dataSourcesCount = 0;
      }
    });
  }

  loadDataDestinations(): void {
    this.configService.get('/data-destination/count').subscribe({
      next: (response: { count: number }) => {
        this.dataDestinationsCount = response?.count || 0;
      },
      error: (error) => {
        console.error('Failed to load data destinations:', error);
        this.dataDestinationsCount = 0;
      }
    });
  }

  loadPipelines(): void {
    this.configService.get('/ingestion-pipelines/').subscribe({
      next: (response: IngestionPipelineSummary[]) => {
        const pipelines = Array.isArray(response) ? response : [];
        this.pipelinesCount = pipelines.length;
        this.runningPipelinesCount = pipelines.filter(p => !!p.nifi_process_group_id).length;
      },
      error: (error) => {
        console.error('Failed to load ingestion pipelines:', error);
        this.pipelinesCount = 0;
        this.runningPipelinesCount = 0;
      }
    });
  }

  navigateTo(path: string): void {
    this.router.navigate([path]);
  }

  openNewNotebook(): void {
    window.open(environment.jupyterUrl, '_blank', 'noopener,noreferrer');
  }
}
