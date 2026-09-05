import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { AvatarModule } from 'primeng/avatar';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { environment } from '../../../environments/environment';

export interface NavItem {
  label: string;
  icon: string;
  route: string;
  external?: boolean;
  url?: string;
}

export interface NavGroup {
  title?: string;
  items: NavItem[];
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, ButtonModule, AvatarModule, RouterLink, RouterLinkActive],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css'
})
export class SidebarComponent {
  isNewMenuOpen = false;
  isMoreOpen = false;
  collapsed = false;
  metabaseUrl = environment.metabaseUrl;

  toggleCollapse(): void {
    this.collapsed = !this.collapsed;
    if (this.collapsed) {
      this.closeDropdown();
    }
  }

  toggleNewMenu(): void {
    this.isNewMenuOpen = !this.isNewMenuOpen;
    if (!this.isNewMenuOpen) this.isMoreOpen = false;
  }

  toggleMore(event: MouseEvent): void {
    event.stopPropagation();
    this.isMoreOpen = !this.isMoreOpen;
  }

  closeDropdown(): void {
    this.isNewMenuOpen = false;
    this.isMoreOpen = false;
  }

  mainItems: NavItem[] = [
    { label: 'Home', icon: 'home', route: '/dashboard' },
    // { label: 'Learn', icon: 'school', route: '/learn' },
    { label: 'Workspace', icon: 'book', route: '/workspace' },
    { label: 'Recents', icon: 'schedule', route: '/recents' },
    { label: 'Catalog', icon: 'change_history', route: '/data-sources' },
    { label: 'Jobs & Pipelines', icon: 'alt_route', route: '/ingestion-pipelines' },
    { label: 'Compute', icon: 'cloud', route: '/compute' },
    { label: 'Discover', icon: 'explore', route: '/discover' },
    { label: 'Marketplace', icon: 'storefront', route: '/marketplace' }
  ];

  sqlItems: NavItem[] = [
    { label: 'SQL Editor', icon: 'terminal', route: '/sql-editor' },
    { label: 'Queries', icon: 'description', route: '/queries' },
    { label: 'Dashboards', icon: 'dashboard', route: '/dashboards', external: true, url: environment.metabaseUrl },
    { label: 'Orbitto', icon: 'smart_toy', route: '/orbitto' },
    { label: 'Alerts', icon: 'notifications_none', route: '/alerts' },
    { label: 'Query History', icon: 'history', route: '/query-history' },
    { label: 'SQL Warehouses', icon: 'cloud_queue', route: '/data-destinations' }
  ];

  dataEngineeringItems: NavItem[] = [
    { label: 'Runs', icon: 'playlist_play', route: '/runs' },
    { label: 'Data Ingestion', icon: 'dataset', route: '/ingestion-pipelines' },
    { label: 'Visual Data Prep', icon: 'dataset_linked', route: '/data-sources' },
    { label: 'Iceberg Catalog', icon: 'inventory_2', route: '/iceberg-catalog' }
  ];

  toolsItems: NavItem[] = [
    { label: 'NiFi', icon: 'alt_route', route: '', external: true, url: environment.nifiUrl },
    { label: 'Kafka UI', icon: 'sync_alt', route: '', external: true, url: environment.kafkaUiUrl },
    { label: 'Spark', icon: 'bolt', route: '', external: true, url: environment.sparkUrl },
    { label: 'Trino', icon: 'query_stats', route: '', external: true, url: environment.trinoUrl },
    { label: 'MinIO Console', icon: 'inventory_2', route: '', external: true, url: environment.minioConsoleUrl },
    { label: 'Grafana', icon: 'monitoring', route: '', external: true, url: environment.grafanaUrl },
    { label: 'Metabase', icon: 'dashboard', route: '', external: true, url: environment.metabaseUrl },
    { label: 'Jupyter Notebook', icon: 'book', route: '', external: true, url: environment.jupyterUrl },
    { label: 'Ranger', icon: 'shield', route: '', external: true, url: environment.rangerUrl }
  ];

  aiMlItems: NavItem[] = [
    { label: 'Playground', icon: 'auto_awesome', route: '/playground' },
    { label: 'Agents', icon: 'support_agent', route: '/agents' },
    { label: 'AI Gateway', icon: 'hub', route: '/ai-gateway' },
    { label: 'Experiments', icon: 'science', route: '/experiments' },
    { label: 'Features', icon: 'dynamic_feed', route: '/features' },
    { label: 'Models', icon: 'bubble_chart', route: '/models' },
    { label: 'Serving', icon: 'cloud_sync', route: '/serving' }
  ];

  constructor(public router: Router) {}
}


