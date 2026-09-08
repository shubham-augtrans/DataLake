import { Routes } from '@angular/router';

import { LoginComponent } from './components/login/login.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { DataSourcesComponent } from './components/data-sources/data-sources.component';
import { DataDestinationComponent } from './components/data-destination/data-destination.component';
import { MainLayoutComponent } from './components/main-layout/main-layout.component';
import { IngestionComponent } from './components/ingestion/ingestion.component';
import { ModuleViewComponent } from './components/module-view/module-view.component';
import { QueryComponent } from './components/query/query.component';
import { TrinoQueryComponent } from './components/trino-query/trino-query.component';
import { IcebergCatalogComponent } from './components/iceberg-catalog/iceberg-catalog.component';
import { PlaygroundComponent } from './components/playground/playground.component';
import { FlowChartComponent } from './components/flow-chart/flow-chart.component';
import { ApiDocsComponent } from './components/api-docs/api-docs.component';

export const routes: Routes = [
  {
    path: '',
    component: LoginComponent,
    pathMatch: 'full'
  },
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      {
        path: 'dashboard',
        component: DashboardComponent
      },
      {
        path: 'data-sources',
        component: DataSourcesComponent
      },
      {
        path: 'data-destinations',
        component: DataDestinationComponent
      },
      {
        path: 'ingestion-pipelines',
        component: IngestionComponent
      },
      // Main Group
      {
        path: 'learn',
        component: ModuleViewComponent,
        data: { title: 'Learn', icon: 'school', description: 'Documentation, quickstarts, and interactive learning guides.' }
      },
      {
        path: 'workspace',
        component: ModuleViewComponent,
        data: { title: 'Workspace', icon: 'book', description: 'Collaborative notebooks, folders, and shared workspace files.' }
      },
      {
        path: 'recents',
        component: ModuleViewComponent,
        data: { title: 'Recents', icon: 'schedule', description: 'Quickly access your recently opened queries, notebooks, and pipelines.' }
      },
      {
        path: 'compute',
        component: ModuleViewComponent,
        data: { title: 'Compute', icon: 'cloud', description: 'Manage compute clusters, serverless engines, and worker nodes.' }
      },
      {
        path: 'discover',
        component: ModuleViewComponent,
        data: { title: 'Discover', icon: 'explore', description: 'Explore organization-wide data assets, dashboards, and shared AI models.' }
      },
      {
        path: 'marketplace',
        component: ModuleViewComponent,
        data: { title: 'Marketplace', icon: 'storefront', description: 'Browse and subscribe to third-party data feeds, connectors, and solution accelerators.' }
      },
      // SQL Group
      {
        path: 'sql-editor',
        component: QueryComponent
      },
      {
        path: 'trino-editor',
        component: TrinoQueryComponent
      },
      {
        path: 'queries',
        component: QueryComponent
      },
      {
        path: 'dashboards',
        component: ModuleViewComponent,
        data: { title: 'Dashboards', icon: 'dashboard', description: 'Interactive visualization dashboards, charts, and KPI reports. Opens in Metabase.' }
      },
      {
        path: 'orbitto',
        component: ModuleViewComponent,
        data: { title: 'Orbitto Agents', icon: 'smart_toy', description: 'AI-assisted natural language data analyst and autonomous workflows powered by Orbitto.' }
      },
      {
        path: 'alerts',
        component: ModuleViewComponent,
        data: { title: 'Alerts', icon: 'notifications_none', description: 'Configure threshold-based alerts and trigger notifications on metric deviations.' }
      },
      {
        path: 'query-history',
        component: ModuleViewComponent,
        data: { title: 'Query History', icon: 'history', description: 'Audit trail of past query executions, runtimes, compute metrics, and error logs.' }
      },
      // Data Engineering Group
      {
        path: 'runs',
        component: ModuleViewComponent,
        data: { title: 'Job Runs', icon: 'playlist_play', description: 'Execution timeline and log inspections for batch and streaming pipelines.' }
      },
      {
        path: 'iceberg-catalog',
        component: IcebergCatalogComponent
      },
      {
        path: 'data-flow',
        component: FlowChartComponent
      },
      // Documentation Group
      {
        path: 'documentation/api',
        component: ApiDocsComponent
      },
      // AI / ML Group
      {
        path: 'playground',
        component: PlaygroundComponent
      },
      {
        path: 'agents',
        component: ModuleViewComponent,
        data: { title: 'Agents', icon: 'support_agent', description: 'Multi-agent orchestration and conversational task executors.' }
      },
      {
        path: 'ai-gateway',
        component: ModuleViewComponent,
        data: { title: 'AI Gateway', icon: 'hub', description: 'Unified API routing, rate limiting, and cost controls for foundation models.' }
      },
      {
        path: 'experiments',
        component: ModuleViewComponent,
        data: { title: 'ML Experiments', icon: 'science', description: 'Track ML model training parameters, metrics, and artifact runs.' }
      },
      {
        path: 'features',
        component: ModuleViewComponent,
        data: { title: 'Feature Store', icon: 'dynamic_feed', description: 'Centralized feature registry and offline-to-online transformations.' }
      },
      {
        path: 'models',
        component: ModuleViewComponent,
        data: { title: 'Model Registry', icon: 'bubble_chart', description: 'Versioned machine learning model registry with deployment governance.' }
      },
      {
        path: 'serving',
        component: ModuleViewComponent,
        data: { title: 'Model Serving', icon: 'cloud_sync', description: 'Deploy and scale low-latency real-time REST endpoints for AI models.' }
      }
    ]
  },
  {
    path: '**',
    redirectTo: ''
  }
];