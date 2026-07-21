import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { DropdownModule } from 'primeng/dropdown';
import { ProgressBarModule } from 'primeng/progressbar';

import { ConfigService } from '../../services/config.service';

interface DataSource {
  id: number;
  name: string;
  endpoint: string;
  username: string;
  password: string;
  created_at: string;
  updated_at: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    CardModule,
    ButtonModule,
    DropdownModule,
    ProgressBarModule
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {

  constructor(private configService: ConfigService) {}

  ngOnInit(): void {
    this.loadDataSources();
    this.loadPipelines();
  }

  rangeOptions = [
    { label: 'Last 7 Days', value: '7' },
    { label: 'Last 30 Days', value: '30' }
  ];

  selectedRange = '7';

  cards = [
    {
      title: 'Data Sources',
      value: '0',
      note: 'Loading...',
      icon: 'pi-database'
    },
    {
      title: 'Storage Used',
      value: '1.2 PB',
      note: '74% capacity',
      icon: 'pi-server'
    },
    {
      title: 'Running Pipelines',
      value: '0',
      note: 'Healthy',
      icon: 'pi-sitemap'
    },
    {
      title: 'AI Requests',
      value: '12.4k',
      note: 'Today',
      icon: 'pi-bolt'
    },
    {
      title: 'Active Agents',
      value: '8',
      note: 'All operational',
      icon: 'pi-users'
    }
  ];

  modelUsage = [
    { name: 'GPT-4 Turbo', value: 62 },
    { name: 'Claude 3 Opus', value: 24 },
    { name: 'Llama 3 70B (Local)', value: 10 },
    { name: 'Embeddings (Ada)', value: 4 }
  ];

  activity = [
    {
      type: 'error',
      title: 'Pipeline Execution Failed: Postgres Sync',
      time: '2 mins ago',
      description:
        "Timeout error connecting to upstream database source 'prod-db-cluster-01'."
    },
    {
      type: 'success',
      title: 'New Agent Deployed: Customer Support Triager',
      time: '45 mins ago',
      description:
        'Agent successfully compiled and deployed to production environment.'
    },
    {
      type: 'info',
      title: 'Vector Database Indexing Completed',
      time: '2 hours ago',
      description:
        'Batch sync processed 1.2M chunks into Pinecone index.'
    }
  ];

  loadDataSources(): void {
    this.configService.get('/data-sources/count').subscribe({
      next: (response: { count: number }) => {
        console.log('Data Sources:', response);

        const count = response.count;

        const dataSourceCard = this.cards.find(
          card => card.title === 'Data Sources'
        );

        if (dataSourceCard) {
          dataSourceCard.value = count.toString();
          dataSourceCard.note = `${count} Connected`;
        }
      },
      error: (error) => {
        console.error('Failed to load data sources:', error);

        const dataSourceCard = this.cards.find(
          card => card.title === 'Data Sources'
        );

        if (dataSourceCard) {
          dataSourceCard.value = '0';
          dataSourceCard.note = 'Unable to load';
        }
      }
    });
  }
  loadPipelines(): void {
    this.configService.get('/ingestion-pipelines/count').subscribe({
      next: (response: { count: number }) => {
        console.log('Ingestion Pipelines:', response);

        const count = response.count;

        const pipelineCard = this.cards.find(
          card => card.title === 'Running Pipelines'
        );

        if (pipelineCard) {
          pipelineCard.value = count.toString();
          pipelineCard.note = `${count} Connected`;
        }
      },
      error: (error) => {
        console.error('Failed to load ingestion pipelines:', error);

        const pipelineCard = this.cards.find(
          card => card.title === 'Running Pipelines'
        );

        if (pipelineCard) {
          pipelineCard.value = '0';
          pipelineCard.note = 'Unable to load';
        }
      }
    });
  }
}