import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';

type BiTool = 'METABASE' | 'SUPERSET';

@Component({
  selector: 'app-visualization-tools',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './visualization-tools.component.html',
  styleUrl: './visualization-tools.component.css'
})
export class VisualizationToolsComponent implements OnInit {

  private readonly API_URL = environment.apiBaseUrl;

  activeBiTool: BiTool = 'METABASE';
  loading = true;
  saving = false;
  saved = false;
  error: string | null = null;

  readonly biTools: { value: BiTool; label: string; description: string; icon: string }[] = [
    {
      value: 'METABASE',
      label: 'Metabase',
      description: 'AI Playground dashboards are built and embedded in Metabase.',
      icon: 'dashboard'
    },
    {
      value: 'SUPERSET',
      label: 'Apache Superset',
      description: 'AI Playground dashboards are built and embedded in Apache Superset instead.',
      icon: 'insights'
    }
  ];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<{ active_bi_tool: BiTool }>(`${this.API_URL}/users/me/preferences/`).subscribe({
      next: (res) => {
        this.activeBiTool = res.active_bi_tool;
        this.loading = false;
      },
      error: () => {
        this.error = 'Could not load your preferences.';
        this.loading = false;
      }
    });
  }

  selectTool(tool: BiTool): void {
    if (tool === this.activeBiTool || this.saving) {
      return;
    }

    this.saving = true;
    this.saved = false;
    this.error = null;

    this.http.patch<{ active_bi_tool: BiTool }>(`${this.API_URL}/users/me/preferences/`, {
      active_bi_tool: tool
    }).subscribe({
      next: (res) => {
        this.activeBiTool = res.active_bi_tool;
        this.saving = false;
        this.saved = true;
      },
      error: () => {
        this.error = 'Could not save your preference. Please try again.';
        this.saving = false;
      }
    });
  }
}
