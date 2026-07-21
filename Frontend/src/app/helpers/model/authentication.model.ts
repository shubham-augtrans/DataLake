// helpers/model/authentication.model.ts
export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UserInfo {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: 'ADMIN' | 'USER' | string;
}

export interface LoginResponse {
  message: string;
  access: string;
  refresh: string;
  user: UserInfo;
}

