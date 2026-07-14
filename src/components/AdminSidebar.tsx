import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';

interface AdminSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminSidebar: React.FC<AdminSidebarProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [isDesktopOpen, setIsDesktopOpen] = useState(true);

  const handleLogout = (): void => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <>
      {!isDesktopOpen && (
        <button
          type="button"
          onClick={() => setIsDesktopOpen(true)}
          className="hidden md:inline-flex fixed left-4 top-5 z-[60] h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-[#0c0f1a] text-slate-300 shadow-xl hover:bg-cyan-500/10 hover:text-cyan-300 hover:border-cyan-400/30 transition-all"
          aria-label="Buka sidebar admin"
          title="Buka sidebar"
        >
          <span className="material-symbols-outlined text-[24px]">chevron_right</span>
        </button>
      )}

      <div
        className={`fixed inset-0 bg-black/80 backdrop-blur-sm z-40 md:hidden transition-opacity duration-300 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      <aside
        className={`fixed md:relative h-full bg-[#05070d] border-r border-white/5 shadow-2xl flex flex-col z-50 shrink-0 transform transition-all duration-300 overflow-hidden ${
          isDesktopOpen
            ? 'md:w-64 md:translate-x-0'
            : 'md:w-0 md:-translate-x-full md:border-r-0 md:shadow-none'
        } w-[280px] ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div className="p-5 md:p-6 flex flex-col h-full w-[280px] md:w-64 overflow-y-auto custom-scrollbar">
          <div className="flex items-center justify-center mb-8 relative">
            <img
              src="/assistant-logo.png"
              alt="Lapis Logo"
              className="w-28 md:w-32 h-auto object-contain shrink-0 drop-shadow-[0_0_15px_rgba(255,255,255,0.1)]"
            />

            <button
              type="button"
              onClick={() => setIsDesktopOpen(false)}
              className="hidden md:inline-flex absolute -right-4 top-1/2 -translate-y-1/2 h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-[#0c0f1a] text-slate-300 shadow-lg hover:bg-cyan-500/10 hover:text-cyan-300 hover:border-cyan-400/30 transition-all"
              aria-label="Tutup sidebar admin"
              title="Tutup sidebar"
            >
              <span className="material-symbols-outlined text-[20px]">chevron_left</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="md:hidden absolute right-0 p-1.5 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors shrink-0"
              aria-label="Tutup sidebar admin"
              title="Tutup sidebar admin"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>

          <nav className="flex-1 flex flex-col gap-5">
            <div className="space-y-2">
              <p className="px-1 font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
                Chat Area
              </p>

              <Link
                to="/"
                onClick={onClose}
                className="flex items-center gap-3 px-4 py-3 rounded-xl font-mono text-sm transition-all duration-200 text-white bg-gradient-to-r from-violet-500/10 to-cyan-500/10 border border-white/10 hover:border-cyan-400/30 hover:shadow-[0_0_20px_rgba(34,211,238,0.1)]"
              >
                <span className="material-symbols-outlined icon-filled text-cyan-300">chat</span>
                Knowledge Chat
              </Link>
            </div>

            <div className="space-y-2 border-t border-white/5 pt-5">
              <p className="px-1 font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
                Admin Tools
              </p>

              <Link
                to="/admin"
                onClick={onClose}
                className="flex items-center gap-3 px-4 py-3 rounded-xl font-mono text-sm transition-all duration-200 text-slate-400 hover:bg-white/5 hover:text-white"
              >
                <span className="material-symbols-outlined">dashboard</span>
                Admin Dashboard
              </Link>

              <Link
                to="/admin/upload"
                onClick={onClose}
                className="flex items-center gap-3 px-4 py-3 rounded-xl font-mono text-sm transition-all duration-200 text-slate-400 hover:bg-white/5 hover:text-white"
              >
                <span className="material-symbols-outlined">upload_file</span>
                Upload File
              </Link>

              <Link
                to="/admin/logs"
                onClick={onClose}
                className="flex items-center gap-3 px-4 py-3 rounded-xl font-mono text-sm transition-all duration-200 text-slate-400 hover:bg-white/5 hover:text-white"
              >
                <span className="material-symbols-outlined">receipt_long</span>
                Query Logs
              </Link>
            </div>
          </nav>

          <div className="mt-6 border-t border-white/5 pt-5">
            <div className="mb-3 rounded-xl bg-[#0c0f1a] border border-white/5 px-4 py-3 shadow-inner">
              <p className="truncate text-sm font-semibold text-slate-200">
                {user?.name ?? user?.username ?? 'Admin'}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-cyan-400 mt-0.5">
                {user?.role ?? 'Administrator'}
              </p>
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 px-4 py-3 rounded-xl font-mono text-sm transition-all duration-200 text-rose-400/80 hover:bg-rose-500/10 hover:text-rose-400"
            >
              <span className="material-symbols-outlined text-[20px]">logout</span>
              Logout
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};