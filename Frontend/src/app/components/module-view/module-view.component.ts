import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-module-view',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="module-page">
      <div class="module-header">
        <div class="header-content">
          <div class="icon-wrapper">
            <span class="material-symbols-outlined">{{ icon }}</span>
          </div>
          <div>
            <h1 class="title">{{ title }}</h1>
            <p class="subtitle">{{ description }}</p>
          </div>
        </div>
        <div class="header-actions">
          <button class="btn btn-primary" type="button">
            <span class="material-symbols-outlined">add</span>
            <span>New {{ title }}</span>
          </button>
        </div>
      </div>

      <div class="module-body">
        <div class="placeholder-card">
          <div class="placeholder-icon">
            <span class="material-symbols-outlined">{{ icon }}</span>
          </div>
          <h2>{{ title }} Workspace</h2>
          <p>This module is connected and active. Configure your workspace parameters or start creating new assets.</p>
          <div class="quick-links">
            <a routerLink="/dashboard" class="quick-btn">
              <span class="material-symbols-outlined">dashboard</span>
              <span>Back to Overview</span>
            </a>
            <a routerLink="/data-sources" class="quick-btn secondary">
              <span class="material-symbols-outlined">database</span>
              <span>View Data Sources</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
      background-color: var(--app-bg);
      color: var(--app-on-surface);
      font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
    }
    .module-page {
      padding: 24px;
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .module-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background-color: var(--app-surface-container);
      border: 1px solid var(--app-outline-variant);
      padding: 20px 24px;
      border-radius: 14px;
    }
    .header-content {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .icon-wrapper {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--app-primary) 0%, #8ca6ff 100%);
      color: var(--app-on-primary);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .icon-wrapper span {
      font-size: 20px;
    }
    .title {
      margin: 0;
      font-size: 19px;
      font-weight: 600;
      color: var(--app-on-surface);
    }
    .subtitle {
      margin: 4px 0 0;
      font-size: 11px;
      color: var(--app-on-surface-variant);
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s ease;
    }
    .btn-primary {
      background-color: var(--app-primary);
      color: var(--app-on-primary);
    }
    .btn-primary:hover {
      background-color: var(--app-primary);
      box-shadow: 0 4px 14px color-mix(in srgb, var(--app-primary) 30%, transparent);
    }
    .placeholder-card {
      background-color: var(--app-surface-container);
      border: 1px dashed var(--app-outline-variant);
      border-radius: 14px;
      padding: 60px 20px;
      text-align: center;
      max-width: 650px;
      margin: 40px auto;
    }
    .placeholder-icon {
      width: 64px;
      height: 64px;
      border-radius: 50%;
      background: color-mix(in srgb, var(--app-primary) 10%, transparent);
      color: var(--app-primary);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 16px;
    }
    .placeholder-icon span {
      font-size: 27px;
    }
    .placeholder-card h2 {
      margin: 0 0 8px;
      font-size: 17px;
      color: var(--app-on-surface);
    }
    .placeholder-card p {
      margin: 0 0 24px;
      color: var(--app-on-surface-variant);
      font-size: 12px;
      line-height: 1.5;
    }
    .quick-links {
      display: flex;
      justify-content: center;
      gap: 12px;
    }
    .quick-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 500;
      text-decoration: none;
      background-color: var(--app-primary);
      color: var(--app-on-primary);
      transition: background 0.2s;
    }
    .quick-btn.secondary {
      background-color: var(--app-surface-container-highest);
      color: var(--app-on-surface);
    }
    .quick-btn:hover {
      opacity: 0.9;
    }
  `]
})
export class ModuleViewComponent implements OnInit {
  title = 'Module';
  description = 'Manage and explore this module in the DataLake platform.';
  icon = 'apps';

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.route.data.subscribe(data => {
      if (data['title']) this.title = data['title'];
      if (data['description']) this.description = data['description'];
      if (data['icon']) this.icon = data['icon'];
    });
  }
}
