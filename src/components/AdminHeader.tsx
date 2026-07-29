import React from 'react';

interface AdminHeaderProps {
  onToggleSidebar: () => void;
}

export const AdminHeader: React.FC<AdminHeaderProps> = ({ onToggleSidebar }) => {
  return (
    <header className="h-14 md:h-16 relative flex items-center px-4 md:px-8 bg-[#05070d] border-b border-white/5 sticky top-0 z-40 shrink-0">
      {/* Tombol menu mobile */}
      <button
        type="button"
        onClick={onToggleSidebar}
        className="md:hidden p-1.5 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors z-10"
        aria-label="Open admin menu"
        title="Open admin menu"
      >
        <span className="material-symbols-outlined">menu</span>
      </button>

      {/* Logo tengah */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none px-16">
        <img
          src="/icon-ungu.png"
          alt="Lapis Logo"
          className="w-20 md:w-24 h-auto object-contain"
        />
      </div>
    </header>
  );
};