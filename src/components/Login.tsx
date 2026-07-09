import React, {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  Navigate,
  useLocation,
  useNavigate,
} from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import type { AuthUser } from '../services/authService';

interface LoginLocationState {
  from?: {
    pathname?: string;
    search?: string;
  };
}

const isAdminRole = (role: string): boolean => {
  return (
    role === 'admin' ||
    role === 'superadmin' ||
    role === 'owner'
  );
};

const resolveRedirectPath = (
  authenticatedUser: AuthUser,
  requestedPath: string
): string => {
  const role = authenticatedUser.role;
  const requestedAdminRoute =
    requestedPath.startsWith('/admin');

  if (!isAdminRole(role) && requestedAdminRoute) {
    return '/';
  }

  if (
    requestedPath &&
    requestedPath !== '/login' &&
    requestedPath !== '/'
  ) {
    return requestedPath;
  }

  return isAdminRole(role) ? '/admin' : '/';
};

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const {
    user,
    isAuthenticated,
    isInitializing,
    login,
  } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] =
    useState(false);
  const [isSubmitting, setIsSubmitting] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);

  const requestedPath = useMemo(() => {
    const state =
      location.state as LoginLocationState | null;

    const pathname = state?.from?.pathname ?? '/';
    const search = state?.from?.search ?? '';

    return `${pathname}${search}`;
  }, [location.state]);

  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    const normalizedUsername = username.trim();

    if (!normalizedUsername || !password) {
      setError('Username dan password wajib diisi.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const authenticatedUser = await login({
        username: normalizedUsername,
        password,
      });

      if (!authenticatedUser?.role) {
        throw new Error(
          'Login berhasil, tetapi data role user tidak terbaca.'
        );
      }

      navigate(
        resolveRedirectPath(
          authenticatedUser,
          requestedPath
        ),
        {
          replace: true,
        }
      );
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : 'Login gagal. Periksa username dan password.';

      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#1e293b] font-body text-on-surface">
        <span className="font-mono text-sm text-on-surface-variant">
          Memeriksa sesi...
        </span>
      </div>
    );
  }

  if (isAuthenticated && user) {
    return (
      <Navigate
        to={resolveRedirectPath(user, requestedPath)}
        replace
      />
    );
  }

  return (
    <div className="flex h-screen items-center justify-center overflow-hidden bg-[#1e293b] px-4 font-body text-on-surface sm:p-6">
      <main className="relative z-10 flex w-full max-w-[400px] animate-fadeIn flex-col gap-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="mb-2 flex h-16 w-16 items-center justify-center rounded-full bg-secondary-container">
            <span className="material-symbols-outlined text-[32px] text-primary">
              hub
            </span>
          </div>

          <h1 className="font-headline text-[32px] font-semibold leading-tight tracking-tight text-on-surface">
            Assistant
          </h1>

          <p className="font-mono text-xs uppercase tracking-[0.22em] text-on-surface-variant">
            Enterprise AI Node
          </p>
        </div>

        <form
          className="flex flex-col gap-6"
          onSubmit={handleSubmit}
        >
          <div className="flex flex-col gap-2">
            <label
              className="ml-1 font-mono text-xs uppercase tracking-wide text-on-surface-variant"
              htmlFor="username"
            >
              Username
            </label>

            <div className="group relative rounded focus-within:shadow-[0_0_0_2px_rgba(59,130,246,0.3)]">
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[20px] text-outline transition-colors group-focus-within:text-primary">
                person
              </span>

              <input
                id="username"
                name="username"
                autoComplete="username"
                className="w-full rounded border border-[#334155] bg-[#111319] py-4 pl-[44px] pr-4 text-on-surface transition-all placeholder:text-outline-variant focus:border-primary focus:ring-0"
                placeholder="Enter your ID"
                type="text"
                value={username}
                onChange={(event) =>
                  setUsername(event.target.value)
                }
                required
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label
              className="ml-1 font-mono text-xs uppercase tracking-wide text-on-surface-variant"
              htmlFor="password"
            >
              Password
            </label>

            <div className="group relative rounded focus-within:shadow-[0_0_0_2px_rgba(59,130,246,0.3)]">
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[20px] text-outline transition-colors group-focus-within:text-primary">
                lock
              </span>

              <input
                id="password"
                name="password"
                autoComplete="current-password"
                className="w-full rounded border border-[#334155] bg-[#111319] py-4 pl-[44px] pr-[44px] text-on-surface transition-all placeholder:text-outline-variant focus:border-primary focus:ring-0"
                placeholder="••••••••"
                type={
                  showPassword ? 'text' : 'password'
                }
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                required
              />

              <button
                type="button"
                onClick={() =>
                  setShowPassword(
                    (currentValue) => !currentValue
                  )
                }
                className="absolute right-4 top-1/2 -translate-y-1/2 text-outline transition-colors hover:text-on-surface focus:outline-none"
                aria-label={
                  showPassword
                    ? 'Sembunyikan password'
                    : 'Tampilkan password'
                }
              >
                <span className="material-symbols-outlined text-[20px]">
                  {showPassword
                    ? 'visibility_off'
                    : 'visibility'}
                </span>
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-error/25 bg-error/10 px-4 py-3 text-sm text-error">
              {error}
            </div>
          )}

          <button
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[#3b82f6] py-4 font-headline text-[15px] font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-[#2563eb] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-75"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <span className="material-symbols-outlined animate-spin text-[20px]">
                  progress_activity
                </span>
                Authenticating...
              </>
            ) : (
              <>
                Log In
                <span className="material-symbols-outlined text-[18px]">
                  login
                </span>
              </>
            )}
          </button>
        </form>

        <div className="mt-4 flex flex-col gap-4 border-t border-outline-variant/30 pt-6">
          <div className="flex items-center justify-center gap-2 text-on-surface-variant">
            <span className="material-symbols-outlined text-[16px]">
              verified_user
            </span>
            <p className="text-sm opacity-60">
              End-to-End Encrypted Session
            </p>
          </div>

          <div className="flex justify-center gap-6">
            <span className="font-mono text-xs text-outline transition-colors hover:text-on-surface">
              Privacy
            </span>
            <span className="font-mono text-xs text-outline transition-colors hover:text-on-surface">
              Terms
            </span>
            <span className="font-mono text-xs text-outline transition-colors hover:text-on-surface">
              v4.2.0
            </span>
          </div>
        </div>
      </main>
    </div>
  );
};