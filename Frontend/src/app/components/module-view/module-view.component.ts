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
      background-color: #11131c;
      color: #e1e1ef;
      font-family: 'Hanken Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
      background-color: #1d1f29;
      border: 1px solid #424655;
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
      background: linear-gradient(135deg, #b4c5ff 0%, #8ca6ff 100%);
      color: #002a78;
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
      color: #e1e1ef;
    }
    .subtitle {
      margin: 4px 0 0;
      font-size: 11px;
      color: #c3c6d8;
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
      background-color: #b4c5ff;
      color: #002a78;
    }
    .btn-primary:hover {
      background-color: #dbe1ff;
      box-shadow: 0 4px 14px rgba(180, 197, 255, 0.3);
    }
    .placeholder-card {
      background-color: #1d1f29;
      border: 1px dashed #424655;
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
      background: rgba(180, 197, 255, 0.1);
      color: #b4c5ff;
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
      color: #e1e1ef;
    }
    .placeholder-card p {
      margin: 0 0 24px;
      color: #c3c6d8;
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
      background-color: #1b66ff;
      color: #ffffff;
      transition: background 0.2s;
    }
    .quick-btn.secondary {
      background-color: #32343e;
      color: #e1e1ef;
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
