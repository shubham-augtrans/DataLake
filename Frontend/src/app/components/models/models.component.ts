import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ConfigService } from '../../services/config.service';

export interface LLMModel {
  id: number;
  name: string;
  api_base: string;
  model_name: string;
  api_key: string;
  ca_cert: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

const EMPTY_FORM = {
  id: null as number | null,
  name: '',
  api_base: '',
  model_name: '',
  api_key: '',
  ca_cert: '',
  is_default: false
};

@Component({
  selector: 'app-models',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './models.component.html',
  styleUrl: './models.component.css'
})
export class ModelsComponent implements OnInit {

  constructor(private configService: ConfigService) {}

  models: LLMModel[] = [];
  loading = false;
  errorMessage = '';

  dialogOpen = false;
  saving = false;
  dialogError = '';
  form = { ...EMPTY_FORM };

  ngOnInit(): void {
    this.loadModels();
  }

  loadModels(): void {
    this.loading = true;
    this.errorMessage = '';

    this.configService.get('/llm-models/').subscribe({
      next: (response: LLMModel[]) => {
        this.loading = false;
        this.models = Array.isArray(response) ? response : [];
      },
      error: (error) => {
        this.loading = false;
        this.errorMessage = error?.error?.detail || 'Failed to load models.';
      }
    });
  }

  get isEditing(): boolean {
    return this.form.id !== null;
  }

  get isFormValid(): boolean {
    return !!(this.form.name.trim() && this.form.api_base.trim() && this.form.model_name.trim());
  }

  certFileName = '';

  openCreateDialog(): void {
    this.form = { ...EMPTY_FORM };
    this.certFileName = '';
    this.dialogError = '';
    this.dialogOpen = true;
  }

  onCertFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      this.form.ca_cert = (reader.result as string) ?? '';
      this.certFileName = file.name;
    };
    reader.onerror = () => {
      this.dialogError = `Failed to read "${file.name}".`;
    };
    reader.readAsText(file);

    input.value = '';
  }

  openEditDialog(model: LLMModel): void {
    this.certFileName = model.ca_cert ? 'Current certificate' : '';
    this.form = {
      id: model.id,
      name: model.name,
      api_base: model.api_base,
      model_name: model.model_name,
      api_key: model.api_key,
      ca_cert: model.ca_cert,
      is_default: model.is_default
    };
    this.dialogError = '';
    this.dialogOpen = true;
  }

  closeDialog(): void {
    this.dialogOpen = false;
  }

  save(): void {
    if (!this.isFormValid) {
      return;
    }

    this.saving = true;
    this.dialogError = '';

    const payload = {
      name: this.form.name.trim(),
      api_base: this.form.api_base.trim(),
      model_name: this.form.model_name.trim(),
      api_key: this.form.api_key.trim(),
      ca_cert: this.form.ca_cert.trim(),
      is_default: this.form.is_default
    };

    const request = this.isEditing
      ? this.configService.patch(`/llm-models/${this.form.id}/`, payload)
      : this.configService.post('/llm-models/', payload);

    request.subscribe({
      next: () => {
        this.saving = false;
        this.dialogOpen = false;
        this.loadModels();
      },
      error: (error) => {
        this.saving = false;
        this.dialogError = error?.error?.detail || 'Failed to save model.';
      }
    });
  }

  setDefault(model: LLMModel): void {
    if (model.is_default) {
      return;
    }

    this.configService.post(`/llm-models/${model.id}/set-default/`, {}).subscribe({
      next: () => this.loadModels(),
      error: (error) => {
        this.errorMessage = error?.error?.detail || 'Failed to set default model.';
      }
    });
  }

  deleteModel(model: LLMModel): void {
    if (!confirm(`Delete "${model.name}"? This can't be undone.`)) {
      return;
    }

    this.configService.delete(`/llm-models/${model.id}/`).subscribe({
      next: () => this.loadModels(),
      error: (error) => {
        this.errorMessage = error?.error?.detail || 'Failed to delete model.';
      }
    });
  }

  maskKey(key: string): string {
    if (!key) {
      return '—';
    }
    return key.length <= 8 ? '••••••••' : `${key.slice(0, 4)}••••${key.slice(-4)}`;
  }
}
