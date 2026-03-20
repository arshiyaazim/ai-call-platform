import { apiGet, apiPost, apiPut, apiDelete } from './api';

export interface ManagedUser {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface UsersResponse {
  users: ManagedUser[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const usersService = {
  list: (page = 1, pageSize = 20) => apiGet<UsersResponse>(`/users?page=${page}&page_size=${pageSize}`),
  create: (data: { username: string; email: string; password: string; role: string }) =>
    apiPost<{ status: string; user_id: string }>('/users/create', data),
  update: (data: { user_id: string; username?: string; email?: string; role?: string; is_active?: boolean }) =>
    apiPut<{ status: string }>('/users/update', data),
  remove: (userId: string) => apiDelete<{ status: string }>(`/users/delete?user_id=${userId}`),
  resetPassword: (userId: string) =>
    apiPost<{ status: string; temporary_password: string }>('/users/reset-password', { user_id: userId }),
};
