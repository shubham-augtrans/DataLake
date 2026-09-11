import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { ConfigService } from '../../../services/config.service';

type Role = 'ADMIN' | 'DATA_ENGINEER' | 'DATA_ANALYST';

interface RoleInfo {
  value: Role;
  label: string;
  icon: string;
  description: string;
  count: number;
}

@Component({
  selector: 'app-access-roles',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './access-roles.component.html',
  styleUrl: './access-roles.component.css'
})
export class AccessRolesComponent implements OnInit {

  loading = true;
  error: string | null = null;

  roles: RoleInfo[] = [
    {
      value: 'ADMIN',
      label: 'Admin',
      icon: 'shield_person',
      description: 'Full access - manages users, roles, and every part of the platform.',
      count: 0,
    },
    {
      value: 'DATA_ENGINEER',
      label: 'Data Engineer',
      icon: 'engineering',
      description: 'Builds and runs ingestion pipelines, manages data sources/destinations and the lakehouse.',
      count: 0,
    },
    {
      value: 'DATA_ANALYST',
      label: 'Data Analyst',
      icon: 'query_stats',
      description: 'Queries data and builds dashboards via the SQL Editor and AI Playground.',
      count: 0,
    },
  ];

  constructor(private configService: ConfigService) {}

  ngOnInit(): void {
    this.configService.get('/users/').subscribe({
      next: (users: { role: Role }[]) => {
        for (const role of this.roles) {
          role.count = users.filter(u => u.role === role.value).length;
        }
        this.loading = false;
      },
      error: () => {
        this.error = 'Could not load role stats.';
        this.loading = false;
      }
    });
  }
}
