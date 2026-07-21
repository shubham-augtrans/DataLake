import { Routes } from '@angular/router';

import { LoginComponent } from './components/login/login.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { DataSourcesComponent } from './components/data-sources/data-sources.component';
import { DataDestinationComponent } from './components/data-destination/data-destination.component';
import { MainLayoutComponent } from './components/main-layout/main-layout.component';
import { IngestionComponent } from './components/ingestion/ingestion.component';
// import { AIStudioComponent } from './components/ai-studio/ai-studio.component';
// import { MonitoringComponent } from './components/monitoring/monitoring.component';

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
      }
      // {
      //   path: 'ai-studio',
      //   component: AIStudioComponent
      // },
      // {
      //   path: 'monitoring',
      //   component: MonitoringComponent
      // }
    ]
  },
  {
    path: '**',
    redirectTo: ''
  }
];