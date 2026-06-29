import { apiClient } from './client';

export interface User {
  id: number;
  email: string;
  role: string;
  dept_name: string;
  dept_key: string | null;
  full_access: boolean;
  is_manager: boolean;
}

export interface LoginResult {
  token: string;
  user: User;
}

export const login = (email: string, password: string) =>
  apiClient.post<{ ok: boolean; data: LoginResult }>('/auth/login/', { email, password });

export const logout = () =>
  apiClient.post('/auth/logout/');

export const getProfile = () =>
  apiClient.get<{ ok: boolean; data: User & { first_name: string; last_name: string } }>(
    '/auth/profile/'
  );
