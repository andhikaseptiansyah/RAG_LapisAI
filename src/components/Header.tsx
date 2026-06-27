import React from 'react';

type DetectedLanguage = 'ID' | 'EN';

interface HeaderProps {
  isOpen: boolean;
  onToggleSidebar: () => void;
  detectedLanguage: DetectedLanguage;
}

export const Header: React.FC<HeaderProps> = ({ isOpen, onToggleSidebar, detectedLanguage }) => {
  const languageLabel = detectedLanguage === 'EN' ? 'English' : 'Indonesia';

  return (
    <header className="h-14 md:h-16 flex justify-between items-center px-4 md:px-6 bg-transparent sticky top-0 z-30 shrink-0">
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
      
      <div className="flex items-center gap-4">
        <div
          className="flex items-center gap-1.5 px-2 md:px-3 py-1.5 rounded-lg bg-surface-container/50 border border-outline-variant text-on-surface-variant text-xs font-mono backdrop-blur-sm"
          title={`AI otomatis mendeteksi bahasa: ${languageLabel}`}
        >
          <span className="material-symbols-outlined text-[16px] md:text-[18px]">translate</span>
          <span className="hidden sm:inline">AUTO</span>
          <span className="text-primary font-bold">{detectedLanguage}</span>
        </div>

        <div className="flex items-center gap-2 md:gap-3 cursor-pointer group border-l border-outline-variant/50 pl-4">
          <div className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-surface-container-high border border-outline flex items-center justify-center overflow-hidden shrink-0">
            <span className="material-symbols-outlined text-sm md:text-base text-on-surface-variant group-hover:text-primary transition-colors">person</span>
          </div>
          <span className="text-xs md:text-sm font-semibold text-on-surface-variant group-hover:text-primary transition-colors hidden sm:block">Staff User</span>
        </div>
      </div>
    </header>
  );
};
