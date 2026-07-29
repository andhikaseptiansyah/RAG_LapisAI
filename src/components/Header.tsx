import React from 'react';

interface HeaderProps {
  isSidebarOpen: boolean;
  isConversationNavigatorOpen: boolean;
  onToggleSidebar: () => void;
  onToggleConversationNavigator: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isSidebarOpen,
  isConversationNavigatorOpen,
  onToggleSidebar,
  onToggleConversationNavigator,
}) => {
  return (
    <header className="pointer-events-none absolute left-0 top-0 z-30 flex h-24 w-full shrink-0 items-center justify-between bg-transparent px-4 md:h-28 md:px-6">
      <button
        type="button"
        onClick={onToggleSidebar}
        className={`pointer-events-auto flex h-12 w-12 items-center justify-center rounded-2xl border backdrop-blur-md transition-all active:scale-95 md:hidden ${
          isSidebarOpen
            ? 'border-white/15 bg-white/10 text-white'
            : 'border-white/10 bg-black/55 text-white/80 hover:border-white/20 hover:bg-white/[0.08]'
        }`}
        title={isSidebarOpen ? 'Tutup menu utama' : 'Buka menu utama'}
        aria-label={isSidebarOpen ? 'Tutup menu utama' : 'Buka menu utama'}
        aria-expanded={isSidebarOpen}
      >
        <svg
          viewBox="0 0 24 24"
          className="h-6 w-6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          {isSidebarOpen ? (
            <>
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </>
          ) : (
            <>
              <path d="M4 7h16" />
              <path d="M4 12h16" />
              <path d="M4 17h16" />
            </>
          )}
        </svg>
      </button>

      <span className="hidden md:block" />

      {!isConversationNavigatorOpen && (
        <button
          type="button"
          onClick={onToggleConversationNavigator}
          className="pointer-events-auto flex h-24 w-24 -translate-y-3 items-center justify-center bg-transparent p-0 transition-opacity hover:opacity-90 focus:outline-none md:h-28 md:w-28 md:-translate-y-4"
          title="Buka isi percakapan"
          aria-label="Buka isi percakapan"
          aria-expanded="false"
        >
          <img
            src="/assistant-logo.png"
            alt=""
            aria-hidden="true"
            className="h-[84px] w-[84px] object-contain md:h-[96px] md:w-[96px]"
          />
        </button>
      )}
    </header>
  );
};

export default Header;
