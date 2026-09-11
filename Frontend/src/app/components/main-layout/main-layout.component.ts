import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterOutlet } from '@angular/router';
import { MenuModule } from 'primeng/menu';
import { MenuItem } from 'primeng/api';

import { SidebarComponent } from '../sidebar/sidebar.component';
import { AuthenticationService } from '../../services/authentication.service';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, SidebarComponent, RouterOutlet, MenuModule],
  templateUrl: './main-layout.component.html',
  styleUrls: ['./main-layout.component.css']
})
export class MainLayoutComponent implements OnInit {

  profileMenuItems: MenuItem[] = [];
  currentUser: any = null;

  constructor(
    private authService: AuthenticationService,
    private router: Router,
    public themeService: ThemeService
  ) {}

  get isDark(): boolean {
    return this.themeService.theme() === 'dark';
  }

  toggleTheme(): void {
    this.themeService.toggle();
  }

  ngOnInit(): void {
    this.currentUser = this.authService.getUser();
    this.initProfileMenu();
  }

  initProfileMenu(): void {
    const userDisplayName = this.currentUser?.first_name
      ? `${this.currentUser.first_name} ${this.currentUser.last_name || ''}`.trim()
      : (this.currentUser?.username || this.currentUser?.email || 'User Profile');

    this.profileMenuItems = [
      {
        label: userDisplayName,
        items: [
          {
            label: 'Profile',
            icon: 'pi pi-user',
            command: () => {
              console.log('Open profile');
            }
          }
        ]
      },
      {
        separator: true
      },
      {
        label: 'Account',
        items: [
          {
            label: 'Logout',
            icon: 'pi pi-sign-out',
            styleClass: 'logout-menu-item',
            command: () => {
              this.onLogout();
            }
          }
        ]
      }
    ];
  }

  onLogout(): void {
    this.authService.logout().subscribe({
      next: () => {
        this.router.navigate(['/login']);
      },
      error: (err) => {
        console.warn('Logout api completed with fallback:', err);
        this.router.navigate(['/login']);
      }
    });
  }
}
