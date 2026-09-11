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

export interface RecentQuery {
  id: number;
  data_source_name: string;
  trino_user: string | null;
  sql_text: string;
  status: 'success' | 'error' | 'denied';
  row_count: number | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
}

interface Activity {
  type: string;
  icon: string;
  title: string;
  time: string;
  description: string;
  tag: string;
  statusText: string;
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

  activities: Activity[] = [];

  constructor(
    private configService: ConfigService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadDataSources();
    this.loadDataDestinations();
    this.loadPipelines();
    this.loadRecentActivities();
  }

  loadRecentActivities(): void {
    this.configService.get('/query/history/recent/').subscribe({
      next: (response: RecentQuery[]) => {
        const queries = Array.isArray(response) ? response : [];
        this.activities = queries.map((q) => this.toActivity(q));
      },
      error: (error) => {
        console.error('Failed to load recent activities:', error);
        this.activities = [];
      }
    });
  }

  private toActivity(q: RecentQuery): Activity {
    const statusMap: Record<RecentQuery['status'], { type: string; title: string; statusText: string }> = {
      success: { type: 'success', title: 'Query executed successfully', statusText: 'Success' },
      error: { type: 'error', title: 'Query execution failed', statusText: 'Failed' },
      denied: { type: 'error', title: 'Query access denied', statusText: 'Denied' }
    };
    const meta = statusMap[q.status];

    return {
      type: meta.type,
      icon: 'terminal',
      title: meta.title,
      time: new Date(q.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      description: q.error_message || q.sql_text,
      tag: q.trino_user || q.data_source_name,
      statusText: meta.statusText
    };
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
      },
      error: (error) => {
        console.error('Failed to load ingestion pipelines:', error);
        this.pipelinesCount = 0;
      }
    });

    // "Currently running" is run-history state (PipelineRun rows with
    // status RUNNING), not a pipeline config field - nifi_process_group_id
    // is a static NiFi flow reference that's set once and stays set after
    // the run finishes (and is never set at all for Google-Drive-sourced
    // pipelines, which use no NiFi flow). Same endpoint Jobs & Pipelines
    // uses, so the two pages agree.
    this.configService.get('/ingestion-pipelines/running/').subscribe({
      next: (runs: unknown[]) => {
        this.runningPipelinesCount = Array.isArray(runs) ? runs.length : 0;
      },
      error: (error) => {
        console.error('Failed to load running pipelines:', error);
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
