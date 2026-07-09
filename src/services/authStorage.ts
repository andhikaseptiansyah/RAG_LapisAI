export type StoredAuthUser = {
  id: string;
  username: string;
  name: string;
  role: string;
};

const TOKEN_KEY = 'lapisai_auth_token';
const USER_KEY = 'lapisai_auth_user';

export const getStoredAuthToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

export const setStoredAuthToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const getStoredAuthUser = (): StoredAuthUser | null => {
  const rawUser = localStorage.getItem(USER_KEY);

  if (!rawUser) {
    return null;
  }

  try {
    return JSON.parse(rawUser) as StoredAuthUser;
  } catch {
    localStorage.removeItem(USER_KEY);
    return null;
  }
};

export const setStoredAuthUser = (
  user: StoredAuthUser
): void => {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

export const setStoredAuth = (
  token: string,
  user: StoredAuthUser
): void => {
  setStoredAuthToken(token);
  setStoredAuthUser(user);
};

export const clearStoredAuth = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

export const hasStoredAuth = (): boolean => {
  return Boolean(
    getStoredAuthToken() && getStoredAuthUser()
  );
};

export const authStorage = {
  getToken: getStoredAuthToken,
  setToken: setStoredAuthToken,
  getUser: getStoredAuthUser,
  setUser: setStoredAuthUser,
  setAuth: setStoredAuth,
  clearAuth: clearStoredAuth,
  isAuthenticated: hasStoredAuth,
};