import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { AvatarModule } from 'primeng/avatar';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { AuthenticationService } from '../../services/authentication.service';

export interface NavItem {
  label: string;
  icon: string;
  route: string;
  external?: boolean;
  url?: string;
  comingSoon?: boolean;
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

  blockIfComingSoon(event: MouseEvent, item: NavItem): void {
    if (item.comingSoon) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  mainItems: NavItem[] = [
    { label: 'Home', icon: 'home', route: '/dashboard' },
    // { label: 'Learn', icon: 'school', route: '/learn' },
    { label: 'Workspace', icon: 'book', route: '/workspace', comingSoon: true },
    { label: 'Recents', icon: 'schedule', route: '/recents', comingSoon: true },
    { label: 'Catalog', icon: 'change_history', route: '/data-sources' },
    { label: 'Jobs & Pipelines', icon: 'alt_route', route: '/jobs' },
    { label: 'Compute', icon: 'cloud', route: '/compute', comingSoon: true },
    { label: 'Discover', icon: 'explore', route: '/discover', comingSoon: true },
    { label: 'Marketplace', icon: 'storefront', route: '/marketplace', comingSoon: true }
  ];

  sqlItems: NavItem[] = [
    { label: 'SQL Editor', icon: 'terminal', route: '/sql-editor' },
    { label: 'Trino Editor', icon: 'query_stats', route: '/trino-editor' },
    { label: 'Queries', icon: 'description', route: '/queries' },
    { label: 'Dashboards', icon: 'dashboard', route: '/dashboards', external: true, url: environment.metabaseUrl },
    { label: 'Orbitto', icon: 'smart_toy', route: '/orbitto', comingSoon: true },
    { label: 'Alerts', icon: 'notifications_none', route: '/alerts', comingSoon: true },
    { label: 'Query History', icon: 'history', route: '/query-history', comingSoon: true },
    { label: 'SQL Warehouses', icon: 'cloud_queue', route: '/data-destinations' }
  ];

  dataEngineeringItems: NavItem[] = [
    { label: 'Runs', icon: 'playlist_play', route: '/runs', comingSoon: true },
    { label: 'Data Ingestion', icon: 'dataset', route: '/ingestion-pipelines' },
    { label: 'Visual Data Prep', icon: 'dataset_linked', route: '/data-sources' },
    { label: 'Iceberg Catalog', icon: 'inventory_2', route: '/iceberg-catalog' },
    { label: 'Data Flow', icon: 'schema', route: '/data-flow' }
  ];

  toolsItems: NavItem[] = [
    { label: 'NiFi', icon: 'alt_route', route: '', external: true, url: environment.nifiUrl },
    { label: 'Kafka UI', icon: 'sync_alt', route: '', external: true, url: environment.kafkaUiUrl },
    { label: 'Spark', icon: 'bolt', route: '', external: true, url: environment.sparkUrl },
    { label: 'Trino', icon: 'query_stats', route: '', external: true, url: environment.trinoUrl },
    { label: 'MinIO Console', icon: 'inventory_2', route: '', external: true, url: environment.minioConsoleUrl },
    { label: 'Grafana', icon: 'monitoring', route: '', external: true, url: environment.grafanaUrl },
    { label: 'Metabase', icon: 'dashboard', route: '', external: true, url: environment.metabaseUrl },
    { label: 'Superset', icon: 'insights', route: '', external: true, url: environment.supersetUrl },
    { label: 'Jupyter Notebook', icon: 'book', route: '', external: true, url: environment.jupyterUrl },
    { label: 'Ranger', icon: 'shield', route: '', external: true, url: environment.rangerUrl },
    { label: 'Airflow', icon: 'schedule', route: '', external: true, url: environment.airflowUrl }
  ];

  documentationItems: NavItem[] = [
    { label: 'API', icon: 'api', route: '/documentation/api' }
  ];

  aiMlItems: NavItem[] = [
    { label: 'Playground', icon: 'auto_awesome', route: '/playground' },
    { label: 'Agents', icon: 'support_agent', route: '/agents', comingSoon: true },
    { label: 'AI Gateway', icon: 'hub', route: '/ai-gateway', comingSoon: true },
    { label: 'Experiments', icon: 'science', route: '/experiments', comingSoon: true },
    { label: 'Features', icon: 'dynamic_feed', route: '/features', comingSoon: true },
    { label: 'Models', icon: 'bubble_chart', route: '/models' },
    { label: 'Serving', icon: 'cloud_sync', route: '/serving', comingSoon: true }
  ];

  // Visualization Tools is a personal preference, open to every user;
  // Users/Access Roles are admin-only both here and on the backend
  // (apps.users.permissions.IsAdmin), so they're hidden rather than
  // shown-then-403'd for anyone else.
  settingsItems: NavItem[] = [
    { label: 'Visualization Tools', icon: 'palette', route: '/settings/visualization-tools' }
  ];

  adminSettingsItems: NavItem[] = [
    { label: 'Users', icon: 'group', route: '/settings/users' },
    { label: 'Access Roles', icon: 'admin_panel_settings', route: '/settings/access-roles' }
  ];

  get isAdmin(): boolean {
    return this.authService.getUser()?.role === 'ADMIN';
  }

  constructor(public router: Router, private authService: AuthenticationService) {}
}


