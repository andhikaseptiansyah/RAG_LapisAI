import React from 'react';
import {
  Navigate,
  useLocation,
} from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';

type ProtectedRouteProps = {
  children: React.ReactNode;
  requireAdmin?: boolean;
};

const isAdminRole = (
  role?: string
): boolean => {
  return (
    role === 'admin' ||
    role === 'superadmin' ||
    role === 'owner'
  );
};

export const ProtectedRoute: React.FC<
  ProtectedRouteProps
> = ({
  children,
  requireAdmin = false,
}) => {
  const location = useLocation();

  const {
    user,
    isAuthenticated,
    isInitializing,
  } = useAuth();

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-white">
        Memeriksa sesi...
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: {
            pathname: location.pathname,
            search: location.search,
          },
        }}
      />
    );
  }

  if (
    requireAdmin &&
    !isAdminRole(user.role)
  ) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
