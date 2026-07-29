import { apiRequest } from './api';

export type AuthRole = 'user' | 'staff' | 'admin';

export interface AuthUser {
  id: string;
  username: string;
  name: string;
  role: AuthRole;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: AuthUser;
}

export interface CurrentUserResponse {
  user: AuthUser;
}

type RawUser = {
  id?: string;
  username?: string;
  name?: string;
  displayName?: string;
  display_name?: string;
  email?: string | null;
  role?: string;
};

type RawLoginPayload = {
  token?: string;
  user?: RawUser;
};

type WrappedLoginResponse = {
  data: RawLoginPayload;
};

type RawLoginResponse =
  | RawLoginPayload
  | WrappedLoginResponse;

type RawCurrentUserPayload = {
  user?: RawUser;
};

type WrappedCurrentUserResponse = {
  data: RawCurrentUserPayload;
};

type RawCurrentUserResponse =
  | RawCurrentUserPayload
  | WrappedCurrentUserResponse;

const isWrappedLoginResponse = (
  response: RawLoginResponse
): response is WrappedLoginResponse => {
  return (
    typeof response === 'object' &&
    response !== null &&
    'data' in response &&
    typeof response.data === 'object' &&
    response.data !== null
  );
};

const isWrappedCurrentUserResponse = (
  response: RawCurrentUserResponse
): response is WrappedCurrentUserResponse => {
  return (
    typeof response === 'object' &&
    response !== null &&
    'data' in response &&
    typeof response.data === 'object' &&
    response.data !== null
  );
};

const normalizeRole = (
  role: string | undefined
): AuthRole => {
  if (role === 'staff') return 'staff';
  if (role === 'admin') return 'admin';
  if (role === 'user') return 'user';

  return 'user';
};

const normalizeUser = (rawUser: RawUser): AuthUser => {
  const id = rawUser.id?.trim() ?? '';
  const username = rawUser.username?.trim() ?? '';

  const name =
    rawUser.name?.trim() ||
    rawUser.displayName?.trim() ||
    rawUser.display_name?.trim() ||
    username ||
    'Pengguna';

  if (!id) {
    throw new Error(
      'Respons login tidak valid: ID pengguna kosong.'
    );
  }

  if (!username) {
    throw new Error(
      'Respons login tidak valid: nama pengguna kosong.'
    );
  }

  return {
    id,
    username,
    name,
    role: normalizeRole(rawUser.role),
  };
};

const normalizeLoginResponse = (
  response: RawLoginResponse
): LoginResponse => {
  const payload: RawLoginPayload =
    isWrappedLoginResponse(response)
      ? response.data
      : response;

  if (!payload.token) {
    throw new Error(
      'Respons login tidak valid: token tidak ditemukan.'
    );
  }

  if (!payload.user) {
    throw new Error(
      'Respons login tidak valid: data pengguna tidak ditemukan.'
    );
  }

  return {
    token: payload.token,
    user: normalizeUser(payload.user),
  };
};

const normalizeCurrentUserResponse = (
  response: RawCurrentUserResponse
): AuthUser => {
  const payload: RawCurrentUserPayload =
    isWrappedCurrentUserResponse(response)
      ? response.data
      : response;

  if (!payload.user) {
    throw new Error(
      'Respons pengguna tidak valid: data pengguna tidak ditemukan.'
    );
  }

  return normalizeUser(payload.user);
};

export const login = async (
  credentials: LoginCredentials
): Promise<LoginResponse> => {
  const response = await apiRequest<
    RawLoginResponse,
    LoginCredentials
  >('/api/auth/login', {
    method: 'POST',
    body: credentials,
    redirectOnUnauthorized: false,
  });

  return normalizeLoginResponse(response);
};

export const getCurrentUser = async (
  token?: string
): Promise<AuthUser> => {
  const response =
    await apiRequest<RawCurrentUserResponse>(
      '/api/auth/me',
      {
        method: 'GET',
        token,
      }
    );

  return normalizeCurrentUserResponse(response);
};