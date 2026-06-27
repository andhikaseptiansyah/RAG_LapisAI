import React from 'react';

interface AdminHeaderProps {
  onToggleSidebar: () => void;
}

export const AdminHeader: React.FC<AdminHeaderProps> = ({ onToggleSidebar }) => {
  return (
    <header className="h-14 md:h-16 flex justify-between items-center px-4 md:px-8 bg-surface/80 backdrop-blur-md border-b border-outline-variant sticky top-0 z-40 shrink-0">
      <div className="flex items-center gap-3 md:gap-6">
        {/* Tombol Menu Mobile */}
        <button onClick={onToggleSidebar} className="md:hidden p-1.5 text-on-surface-variant hover:text-primary hover:bg-surface-container-high rounded-lg transition-colors">
          <span className="material-symbols-outlined">menu</span>
        </button>
        <h2 className="font-headline text-lg md:text-xl font-bold text-on-surface">Admin Dashboard</h2>
      </div>

      <div className="flex items-center justify-end">
        <img
          src="/assistant-logo.png"
          alt="Lapis Logo"
          className="w-20 md:w-24 h-auto object-contain"
        />
      </div>
    </header>
  );
};
