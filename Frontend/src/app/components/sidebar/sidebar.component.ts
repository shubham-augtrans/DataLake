import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { AvatarModule } from 'primeng/avatar';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, ButtonModule, AvatarModule,RouterLink, RouterLinkActive],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css'
})
export class SidebarComponent {
menuItems = [
  {
    label: 'Dashboard',
    icon: 'pi pi-th-large',
    route: '/dashboard'
  },
  {
    label: 'Data Sources',
    icon: 'pi pi-database',
    route: '/data-sources'
  },
    {
    label: 'Data Destinations',
    icon: 'pi pi-database',
    route: '/data-destinations'
  },
      {
    label: 'Ingestion Pipelines',
    icon: 'pi pi-database',
    route: '/ingestion-pipelines'
  },
  // {
  //   label: 'AI Studio',
  //   icon: 'pi pi-microchip-ai',
  //   route: '/ai-studio'
  // },
  // {
  //   label: 'Monitoring',
  //   icon: 'pi pi-chart-line',
  //   route: '/monitoring'
  // }
];
}