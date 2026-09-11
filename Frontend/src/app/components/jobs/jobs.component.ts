import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription, interval, startWith, switchMap } from 'rxjs';

import { TagModule } from 'primeng/tag';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ConfigService } from '../../services/config.service';

export type RunStatus = 'RUNNING' | 'SUCCESS' | 'FAILED';

export interface PipelineRun {
  id: number;
  pipeline: number;
  pipeline_name: string;
  status: RunStatus;
  triggered_by: string;
  message: string | null;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number;
}

const POLL_INTERVAL_MS = 5000;

@Component({
  selector: 'app-jobs',
  standalone: true,
  imports: [CommonModule, TagModule, ProgressSpinnerModule],
  templateUrl: './jobs.component.html',
  styleUrl: './jobs.component.css'
})
export class JobsComponent implements OnInit, OnDestroy {

  runningPipelines: PipelineRun[] = [];
  recentRuns: PipelineRun[] = [];
  loading = true;
  error: string | null = null;

  private pollSubscription?: Subscription;

  constructor(private configService: ConfigService) {}

  ngOnInit(): void {
    // Runs are synchronous on the backend (a pipeline is only "RUNNING"
    // for the lifetime of its /run/ request), so this page polls rather
    // than relying on a single load to reflect live state.
    this.pollSubscription = interval(POLL_INTERVAL_MS).pipe(
      startWith(0),
      switchMap(() => this.configService.get('/ingestion-pipelines/running/'))
    ).subscribe({
      next: (runs: PipelineRun[]) => {
        this.runningPipelines = runs;
        this.loading = false;
        this.error = null;
      },
      error: () => {
        this.error = 'Could not load currently running pipelines.';
        this.loading = false;
      }
    });

    this.loadRecentRuns();
  }

  ngOnDestroy(): void {
    this.pollSubscription?.unsubscribe();
  }

  loadRecentRuns(): void {
    this.configService.get('/ingestion-pipelines/runs/').subscribe({
      next: (runs: PipelineRun[]) => this.recentRuns = runs,
      error: () => {}
    });
  }

  statusSeverity(status: RunStatus): 'info' | 'success' | 'danger' {
    if (status === 'RUNNING') return 'info';
    if (status === 'SUCCESS') return 'success';
    return 'danger';
  }
}
