import React from 'react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose, onNewChat }) => {
  return (
    <>
      {/* Overlay layar gelap khusus untuk mode Mobile */}
      <div 
        className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0 hidden'}`} 
        onClick={onClose}
      />
      
      {/* Container Utama Sidebar */}
      <aside 
        className={`absolute md:relative h-full bg-surface-container shadow-2xl md:shadow-sm flex flex-col z-50 shrink-0 transform transition-all duration-300 overflow-hidden
          ${isOpen 
            ? 'translate-x-0 w-[280px] md:w-64 p-5 md:p-6 opacity-100 border-r border-outline-variant' 
            : '-translate-x-full md:translate-x-0 w-[280px] md:w-0 p-0 opacity-0 border-none'
          }
        `}
      >
        {/* Header Sidebar (Logo & Judul) */}
        <div className="flex items-center justify-between mb-8 min-w-[200px]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 md:w-10 md:h-10 bg-primary-container rounded flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-on-primary-container icon-filled">psychology</span>
            </div>
            <div className="whitespace-nowrap">
              <h1 className="font-headline text-lg md:text-xl font-bold text-primary leading-tight">Assistant</h1>
              <p className="font-mono text-[10px] md:text-xs text-on-surface-variant tracking-wider uppercase">Enterprise AI</p>
            </div>
          </div>
          
          {/* Tombol Tutup (Hanya Muncul di Mobile) */}
          <button onClick={onClose} className="md:hidden p-1 text-on-surface-variant hover:text-primary rounded-lg transition-colors shrink-0">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Menu Navigasi */}
        <nav className="flex flex-col gap-2 min-w-[200px]">
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-primary bg-secondary-container whitespace-nowrap cursor-default">
            <span className="material-symbols-outlined icon-filled">chat</span>
            Knowledge Chat
          </div>
          
          <button onClick={onNewChat} className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-on-surface-variant hover:bg-surface-container-high hover:text-primary whitespace-nowrap w-full text-left">
            <span className="material-symbols-outlined">add_circle</span>
            Percakapan Baru
          </button>
        </nav>

        {/* Daftar Riwayat Chat */}
        <div className="mt-6 pt-4 border-t border-outline-variant flex-1 overflow-y-auto custom-scrollbar min-w-[200px]">
          <p className="text-[10px] font-mono text-outline mb-3 px-2 uppercase tracking-wider">Recent Chats</p>
          <div className="flex flex-col gap-1">
            <button className="text-left px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high hover:text-primary transition-colors rounded-lg truncate flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px] shrink-0">chat_bubble</span> Format Laporan Keuangan
            </button>
            <button className="text-left px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high hover:text-primary transition-colors rounded-lg truncate flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px] shrink-0">chat_bubble</span> Kebijakan Klaim Medis
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};