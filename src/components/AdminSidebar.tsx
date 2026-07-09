import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';

interface AdminSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminSidebar: React.FC<AdminSidebarProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = (): void => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />

      <aside className={`fixed md:relative h-full bg-surface-container border-r border-outline-variant shadow-sm flex flex-col z-50 shrink-0 transform transition-transform duration-300 w-[280px] md:w-64 ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="p-5 md:p-6 flex flex-col h-full overflow-y-auto custom-scrollbar">
          <div className="flex items-center justify-center mb-1 relative">
            <img
              src="/assistant-logo.png"
              alt="Lapis Logo"
              className="w-28 md:w-36 h-auto object-contain shrink-0"
            />

            <button
              type="button"
              onClick={onClose}
              className="md:hidden absolute right-0 p-1 text-on-surface-variant hover:text-primary rounded-lg transition-colors shrink-0"
              aria-label="Tutup sidebar admin"
              title="Tutup sidebar admin"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>

          <nav className="flex-1 flex flex-col gap-2 -mt-1">
            <Link
              to="/"
              onClick={onClose}
              className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-[#0b1b35] bg-[#a8c7fa] hover:bg-[#b7d2ff] shadow-[0_8px_24px_rgba(168,199,250,0.18)]"
            >
              <span className="material-symbols-outlined icon-filled">chat</span>
              Knowledge Chat
            </Link>

            <Link
              to="/admin"
              onClick={onClose}
              className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-on-surface-variant hover:bg-surface-container-high hover:text-primary"
            >
              <span className="material-symbols-outlined">dashboard</span>
              Admin Dashboard
            </Link>

            <Link
              to="/admin/upload"
              onClick={onClose}
              className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-on-surface-variant hover:bg-surface-container-high hover:text-primary"
            >
              <span className="material-symbols-outlined">upload_file</span>
              Upload File
            </Link>

            <Link
              to="/admin/logs"
              onClick={onClose}
              className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-on-surface-variant hover:bg-surface-container-high hover:text-primary"
            >
              <span className="material-symbols-outlined">receipt_long</span>
              Query Logs
            </Link>
          </nav>

          <div className="mt-6 border-t border-outline-variant pt-4">
            <div className="mb-3 rounded-xl bg-surface-container-high px-3 py-3">
              <p className="truncate text-sm text-on-surface">
                {user?.name ?? user?.username ?? 'Admin'}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-on-surface-variant">
                {user?.role ?? 'admin'}
              </p>
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-on-surface-variant hover:bg-surface-container-high hover:text-primary"
            >
              <span className="material-symbols-outlined">logout</span>
              Logout
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};
