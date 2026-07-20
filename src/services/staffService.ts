import { apiRequest } from './api';
import type { AuthRole } from './authService';

export interface ManagedUser {
  id: string;
  username: string;
  name: string;
  role: AuthRole;
  totalChats: number;
  createdAt: string;
  updatedAt: string;
}

export interface ManagedUserListResponse {
  users: ManagedUser[];
  total: number;
  totalChats: number;
}

export interface CreateStaffPayload {
  username: string;
  name: string;
  password: string;
}

export interface PasswordUpdateResponse {
  message: string;
  user: Pick<ManagedUser, 'id' | 'username' | 'name' | 'role'>;
}

export const getManagedUsers = async (
  signal?: AbortSignal
): Promise<ManagedUserListResponse> => {
  return apiRequest<ManagedUserListResponse>(
    '/api/admin/users',
    {
      method: 'GET',
      signal,
    }
  );
};

export const createStaffAccount = async (
  payload: CreateStaffPayload
): Promise<ManagedUser> => {
  return apiRequest<ManagedUser>(
    '/api/admin/users',
    {
      method: 'POST',
      body: payload,
    }
  );
};

export const updateManagedUserPassword = async (
  userId: string,
  password: string
): Promise<PasswordUpdateResponse> => {
  return apiRequest<PasswordUpdateResponse>(
    `/api/admin/users/${encodeURIComponent(userId)}/password`,
    {
      method: 'PATCH',
      body: { password },
    }
  );
};

export const deleteManagedUser = async (
  userId: string
): Promise<void> => {
  await apiRequest<null>(
    `/api/admin/users/${encodeURIComponent(userId)}`,
    {
      method: 'DELETE',
    }
  );
};
