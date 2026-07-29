import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  clearStoredAuth,
  getStoredAuthToken,
  getStoredAuthUser,
  setStoredAuth,
} from '../services/authStorage';

import {
  login as loginRequest,
  type AuthUser,
  type LoginCredentials,
} from '../services/authService';

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  isAdmin: boolean;
  login: (
    credentials: LoginCredentials
  ) => Promise<AuthUser>;
  logout: () => void;
};

const AuthContext =
  createContext<AuthContextValue | undefined>(undefined);

const isAdminRole = (
  role?: string
): boolean => {
  return role === 'admin';
};

const normalizeStoredUser = (
  storedUser: ReturnType<typeof getStoredAuthUser>
): AuthUser | null => {
  if (!storedUser) {
    return null;
  }

  const role =
    storedUser.role === 'user' ||
    storedUser.role === 'staff' ||
    storedUser.role === 'admin'
      ? storedUser.role
      : 'user';

  return {
    id: storedUser.id,
    username: storedUser.username,
    name:
      storedUser.name ||
      storedUser.username ||
      'Pengguna',
    role,
  };
};

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [token, setToken] =
    useState<string | null>(() => {
      return getStoredAuthToken();
    });

  const [user, setUser] =
    useState<AuthUser | null>(() => {
      return normalizeStoredUser(
        getStoredAuthUser()
      );
    });

  const [isInitializing] = useState(false);

  const isAuthenticated = Boolean(token && user);

  const isAdmin = isAdminRole(user?.role);

  const login = async (
    credentials: LoginCredentials
  ): Promise<AuthUser> => {
    const result = await loginRequest(credentials);

    if (!result.token || !result.user) {
      throw new Error(
        'Respons login dari server tidak lengkap.'
      );
    }

    setStoredAuth(result.token, result.user);
    setToken(result.token);
    setUser(result.user);

    return result.user;
  };

  const logout = (): void => {
    clearStoredAuth();
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  };

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated,
      isInitializing,
      isAdmin,
      login,
      logout,
    }),
    [
      user,
      token,
      isAuthenticated,
      isInitializing,
      isAdmin,
    ]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      'useAuth harus digunakan di dalam AuthProvider.'
    );
  }

  return context;
}