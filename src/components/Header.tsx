import React from 'react';

type DetectedLanguage = 'ID' | 'EN';

interface HeaderProps {
  isOpen: boolean;
  onToggleSidebar: () => void;
  detectedLanguage: DetectedLanguage;
}

export const Header: React.FC<HeaderProps> = ({
  isOpen,
  onToggleSidebar,
}) => {
  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between bg-transparent px-4 md:h-20 md:px-6">
      {/* Tombol buka/tutup sidebar */}
      <button
        type="button"
        onClick={onToggleSidebar}
        className="flex h-12 w-12 items-center justify-center text-white/80 transition-all hover:text-white active:scale-95 md:h-14 md:w-14"
        title={isOpen ? 'Tutup sidebar' : 'Buka sidebar'}
        aria-label={isOpen ? 'Tutup sidebar' : 'Buka sidebar'}
      >
        {isOpen ? (
          /* Saat sidebar terbuka: pakai icon biasa */
          <span className="material-symbols-outlined text-[30px] md:text-[32px]">
            menu_open
          </span>
        ) : (
          /* Saat sidebar tertutup: pakai image icon.png di mobile + desktop */
          <img
            src="/icon.png"
            alt="Buka menu"
            className="pointer-events-none h-9 w-9 object-contain md:h-10 md:w-10"
          />
        )}
      </button>
    </header>
  );
};