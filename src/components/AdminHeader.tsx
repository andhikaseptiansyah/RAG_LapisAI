import React from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';

interface AdminHeaderProps {
  onToggleSidebar: () => void;
}

export const AdminHeader: React.FC<AdminHeaderProps> = ({ onToggleSidebar }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = (): void => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="h-14 md:h-16 flex justify-between items-center px-4 md:px-8 bg-surface/80 backdrop-blur-md border-b border-outline-variant sticky top-0 z-40 shrink-0">
      <div className="flex items-center gap-3 md:gap-6">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="md:hidden p-1.5 text-on-surface-variant hover:text-primary hover:bg-surface-container-high rounded-lg transition-colors"
          aria-label="Buka menu admin"
          title="Buka menu admin"
        >
          <span className="material-symbols-outlined">menu</span>
        </button>

        <div>
          <h2 className="font-headline text-lg md:text-xl font-bold text-on-surface">
            Admin Dashboard
          </h2>
          <p className="hidden sm:block text-xs text-on-surface-variant">
            Masuk sebagai {user?.name ?? user?.username ?? 'Admin'}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3">
        <img
          src="/assistant-logo.png"
          alt="Lapis Logo"
          className="w-20 md:w-24 h-auto object-contain"
        />

        <button
          type="button"
          onClick={handleLogout}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-outline-variant bg-surface-container-high text-on-surface-variant transition-colors hover:text-primary"
          title="Logout"
          aria-label="Logout"
        >
          <span className="material-symbols-outlined text-[20px]">
            logout
          </span>
        </button>
      </div>
    </header>
  );
};
