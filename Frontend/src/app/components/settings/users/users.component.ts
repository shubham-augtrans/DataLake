import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { DropdownModule } from 'primeng/dropdown';
import { InputTextModule } from 'primeng/inputtext';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ConfigService } from '../../../services/config.service';

export type Role = 'ADMIN' | 'DATA_ENGINEER' | 'DATA_ANALYST';

export interface AppUser {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: Role;
  active_bi_tool: 'METABASE' | 'SUPERSET';
  is_active: boolean;
  created_at: string;
}

interface UserForm {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: Role;
  password: string;
}

const EMPTY_FORM: UserForm = {
  first_name: '', last_name: '', email: '', phone: '', role: 'DATA_ANALYST', password: '',
};

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    DialogModule,
    DropdownModule,
    InputTextModule,
    TableModule,
    TagModule,
    ProgressSpinnerModule,
  ],
  templateUrl: './users.component.html',
  styleUrl: './users.component.css'
})
export class UsersComponent implements OnInit {

  users: AppUser[] = [];
  loading = true;
  error: string | null = null;

  readonly roleOptions: { label: string; value: Role }[] = [
    { label: 'Admin', value: 'ADMIN' },
    { label: 'Data Engineer', value: 'DATA_ENGINEER' },
    { label: 'Data Analyst', value: 'DATA_ANALYST' },
  ];

  dialogVisible = false;
  editingUser: AppUser | null = null;
  form: UserForm = { ...EMPTY_FORM };
  saving = false;
  formError: string | null = null;

  deleteTarget: AppUser | null = null;

  constructor(private configService: ConfigService) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.loading = true;
    this.error = null;
    this.configService.get('/users/').subscribe({
      next: (res) => {
        this.users = res;
        this.loading = false;
      },
      error: () => {
        this.error = 'Could not load users.';
        this.loading = false;
      }
    });
  }

  roleLabel(role: Role): string {
    return this.roleOptions.find(r => r.value === role)?.label ?? role;
  }

  openCreate(): void {
    this.editingUser = null;
    this.form = { ...EMPTY_FORM };
    this.formError = null;
    this.dialogVisible = true;
  }

  openEdit(user: AppUser): void {
    this.editingUser = user;
    this.form = {
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      phone: user.phone,
      role: user.role,
      password: '',
    };
    this.formError = null;
    this.dialogVisible = true;
  }

  closeDialog(): void {
    this.dialogVisible = false;
  }

  save(): void {
    if (this.saving) {
      return;
    }

    if (!this.editingUser && !this.form.password.trim()) {
      this.formError = 'Password is required when creating a user.';
      return;
    }

    this.saving = true;
    this.formError = null;

    const payload: any = {
      first_name: this.form.first_name,
      last_name: this.form.last_name,
      email: this.form.email,
      phone: this.form.phone,
      role: this.form.role,
    };
    if (this.form.password.trim()) {
      payload.password = this.form.password.trim();
    }

    const request = this.editingUser
      ? this.configService.put(`/users/${this.editingUser.id}/`, payload)
      : this.configService.post('/users/', payload);

    request.subscribe({
      next: () => {
        this.saving = false;
        this.dialogVisible = false;
        this.loadUsers();
      },
      error: (err) => {
        this.saving = false;
        this.formError = err?.error?.email?.[0] || err?.error?.phone?.[0] || err?.error?.password?.[0]
          || 'Could not save this user. Check the fields and try again.';
      }
    });
  }

  confirmDelete(user: AppUser): void {
    this.deleteTarget = user;
  }

  cancelDelete(): void {
    this.deleteTarget = null;
  }

  deleteUser(): void {
    if (!this.deleteTarget) {
      return;
    }
    const target = this.deleteTarget;
    this.configService.delete(`/users/${target.id}/`).subscribe({
      next: () => {
        this.deleteTarget = null;
        this.loadUsers();
      },
      error: () => {
        this.error = 'Could not delete this user.';
        this.deleteTarget = null;
      }
    });
  }
}
