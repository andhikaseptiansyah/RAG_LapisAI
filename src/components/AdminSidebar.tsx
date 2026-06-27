import React from 'react';
import { Link } from 'react-router-dom';

interface AdminSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminSidebar: React.FC<AdminSidebarProps> = ({ isOpen, onClose }) => {
  return (
    <>
      {/* Overlay Gelap Khusus Mobile */}
      <div 
        className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`} 
        onClick={onClose}
      />

      {/* Kontainer Sidebar */}
      <aside className={`fixed md:relative h-full bg-surface-container border-r border-outline-variant shadow-sm flex flex-col z-50 shrink-0 transform transition-transform duration-300 w-[280px] md:w-64 ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        
        <div className="p-5 md:p-6 flex flex-col h-full overflow-y-auto custom-scrollbar">
          {/* Header Sidebar */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 md:w-10 md:h-10 bg-primary-container rounded flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-on-primary-container icon-filled">psychology</span>
              </div>
              <div>
                <h1 className="font-headline text-lg md:text-xl font-bold text-primary leading-tight">Assistant</h1>
                <p className="font-mono text-[10px] md:text-xs text-on-surface-variant tracking-wider uppercase">Enterprise AI</p>
              </div>
            </div>
            {/* Tombol Tutup Sidebar di Mobile */}
            <button onClick={onClose} className="md:hidden p-1 text-on-surface-variant hover:text-primary rounded-lg transition-colors shrink-0">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>

          <nav className="flex-1 flex flex-col gap-2">
            <Link to="/" className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-on-surface-variant hover:bg-surface-container-high">
              <span className="material-symbols-outlined">chat</span>
              Knowledge Chat
            </Link>

            <div className="flex items-center gap-3 px-4 py-3 rounded-lg font-mono text-sm transition-all duration-200 text-primary bg-secondary-container cursor-default">
              <span className="material-symbols-outlined icon-filled">dashboard</span>
              Admin Dashboard
            </div>
          </nav>

          <div className="mt-auto flex flex-col gap-2 pt-6 border-t border-outline-variant">
            <button className="flex items-center gap-3 px-4 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high transition-colors rounded-lg text-left">
              <span className="material-symbols-outlined text-lg">settings</span> Settings
            </button>
            <button className="w-full mt-4 bg-surface-variant py-2.5 rounded-lg text-sm font-semibold text-on-surface hover:bg-outline-variant transition-colors">
              Contact Support
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};