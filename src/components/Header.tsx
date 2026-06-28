import React from 'react';

type DetectedLanguage = 'ID' | 'EN';

interface HeaderProps {
  isOpen: boolean;
  onToggleSidebar: () => void;
  detectedLanguage: DetectedLanguage;
}

export const Header: React.FC<HeaderProps> = ({ isOpen, onToggleSidebar }) => {
  return (
    <header className="h-16 md:h-20 flex justify-between items-center px-4 md:px-6 bg-transparent sticky top-0 z-30 shrink-0">
      <div className="flex items-center gap-3 md:gap-4">
        <button
          onClick={onToggleSidebar}
          className={`p-1.5 md:p-2 text-on-surface-variant hover:text-primary rounded-lg transition-colors flex items-center justify-center ${!isOpen ? 'bg-surface-container-high' : 'hover:bg-surface-container-high'}`}
          title={isOpen ? 'Tutup sidebar' : 'Buka sidebar'}
        >
          <span className="material-symbols-outlined">
            {isOpen ? 'menu_open' : 'menu'}
          </span>
        </button>
      </div>

      <div className="flex items-center">
        <img
          src="/assistant-logo.png"
          alt="Assistant Logo"
          className="h-20 md:h-24 max-w-[300px] object-contain"
        />
      </div>
    </header>
  );
};
