import React, { useState, useEffect, useRef } from 'react';
import { AttachedFile } from '../types';

type UploadMode = 'photo' | 'file';

interface WelcomeScreenProps {
  onSendMessage: (text: string, files: AttachedFile[]) => void;
  onAttachFileClick: (mode: UploadMode) => void;
  onMicClick: () => void;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onSendMessage, onAttachFileClick, onMicClick }) => {
  const [inputValue, setInputValue] = useState('');
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);
  const [placeholder, setPlaceholder] = useState('Minta Assistant...');
  const inputRef = useRef<HTMLInputElement>(null);

  // Typewriter effect logic
  useEffect(() => {
    const placeholders = [
      "Lapis AI Assistant ...",
      "Minta Assistant...",
      "Cari SOP Klaim Medis...",
      "Bantu saya menganalisis data...",
      "Tampilkan Kebijakan WFH..."
    ];
    let phIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    let typeTimer: ReturnType<typeof setTimeout>;

    const typePlaceholder = () => {
      if (document.activeElement === inputRef.current || inputValue !== '') return;
      
      const currentText = placeholders[phIndex];
      if (isDeleting) {
        setPlaceholder(currentText.substring(0, charIndex - 1));
        charIndex--;
      } else {
        setPlaceholder(currentText.substring(0, charIndex + 1));
        charIndex++;
      }

      let typeSpeed = isDeleting ? 30 : 70;
      if (!isDeleting && charIndex === currentText.length) {
        typeSpeed = 2000;
        isDeleting = true;
      } else if (isDeleting && charIndex === 0) {
        isDeleting = false;
        phIndex = (phIndex + 1) % placeholders.length;
        typeSpeed = 500;
      }
      typeTimer = setTimeout(typePlaceholder, typeSpeed);
    };

    typeTimer = setTimeout(typePlaceholder, 500);
    return () => clearTimeout(typeTimer);
  }, [inputValue]);

  const handleSend = () => {
    if (inputValue.trim()) {
      onSendMessage(inputValue, []);
      setInputValue('');
    }
  };

  const handleSuggestionClick = (text: string) => {
    onSendMessage(text, []);
  };

  const handleUploadOptionClick = (mode: UploadMode) => {
    setAttachMenuOpen(false);
    onAttachFileClick(mode);
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center w-full max-w-3xl mx-auto -mt-16 animate-fadeIn">
      <div className="mb-6 flex items-center justify-center animate-[pulse_3s_ease-in-out_infinite]">
        <img
          src="/assistant-logo.png"
          alt="Lapis Logo"
          className="w-24 md:w-32 h-auto object-contain"
        />
      </div>

      <h1 className="text-[26px] md:text-4xl font-headline text-on-surface mb-8 text-center tracking-tight">Apa yang bisa saya bantu, Staff User?</h1>
      
      <div className="relative w-full max-w-[700px] bg-welcome-gradient hover:brightness-110 rounded-[32px] flex items-center shadow-[0_4px_30px_rgba(0,0,0,0.3)] border border-transparent focus-within:border-outline-variant/40 transition-all duration-300 focus-within:brightness-110">
        <input 
          ref={inputRef}
          type="text" 
          className="w-full bg-transparent border-none focus:ring-0 text-on-surface placeholder:text-on-surface-variant/70 text-[15px] md:text-[17px] py-3.5 md:py-4 pl-[72px] pr-[96px] rounded-[32px] outline-none" 
          placeholder={placeholder}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          onFocus={() => setPlaceholder('Ketik sesuatu...')}
        />
        
        <div className="absolute left-2 flex items-center">
          <div className="relative">
            <button
              type="button"
              onClick={() => setAttachMenuOpen((prev) => !prev)}
              className="w-10 h-10 text-outline hover:text-primary hover:bg-surface-variant transition-colors rounded-full flex items-center justify-center"
              title="Tambah lampiran"
            >
              <span className="material-symbols-outlined text-[22px]">add</span>
            </button>

            {attachMenuOpen && (
              <div className="absolute left-0 bottom-full mb-3 w-48 bg-surface-container-high border border-outline-variant rounded-2xl shadow-[0_12px_40px_rgba(0,0,0,0.45)] p-2 z-20 animate-fadeIn">
                <button
                  type="button"
                  onClick={() => handleUploadOptionClick('photo')}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors text-left"
                >
                  <span className="material-symbols-outlined text-[20px]">add_photo_alternate</span>
                  Upload Foto
                </button>

                <button
                  type="button"
                  onClick={() => handleUploadOptionClick('file')}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors text-left"
                >
                  <span className="material-symbols-outlined text-[20px]">description</span>
                  Upload File
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="absolute right-2 flex items-center gap-1">
          <button onClick={onMicClick} className="w-10 h-10 text-outline hover:text-primary hover:bg-surface-variant transition-colors rounded-full flex items-center justify-center" title="Voice to Text">
            <span className="flex items-center justify-center gap-[2px] w-5 h-5" aria-hidden="true">
              <span className="w-[2px] h-2.5 bg-current rounded-full"></span>
              <span className="w-[2px] h-4 bg-current rounded-full"></span>
              <span className="w-[2px] h-5 bg-current rounded-full"></span>
              <span className="w-[2px] h-4 bg-current rounded-full"></span>
              <span className="w-[2px] h-2.5 bg-current rounded-full"></span>
            </span>
          </button>
          <button onClick={handleSend} className="w-10 h-10 bg-primary hover:bg-primary-container text-on-primary-container transition-all active:scale-95 rounded-full flex items-center justify-center shadow-sm ml-1">
            <span className="material-symbols-outlined icon-filled text-[20px] md:text-[22px]">send</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:flex md:flex-wrap justify-center gap-2 md:gap-3 mt-6 md:mt-8 w-full max-w-[700px] px-4 md:px-0 animate-[fadeIn_0.7s_ease-out]">
        {[
          {
            text: 'Cari dan jelaskan prosedur klaim medis berdasarkan dokumen SOP yang tersedia di knowledge base.',
            icon: 'health_and_safety',
            label: 'Cari SOP Klaim Medis',
          },
          {
            text: 'Ringkas dokumen HR terbaru yang tersedia di knowledge base, termasuk poin penting, aturan utama, dan informasi yang perlu diperhatikan karyawan.',
            icon: 'summarize',
            label: 'Ringkas Dokumen HR',
          },
          {
            text: 'Tampilkan dan jelaskan kebijakan work from home yang berlaku berdasarkan dokumen perusahaan yang tersedia.',
            icon: 'home_work',
            label: 'Tampilkan Kebijakan WFH',
          },
          {
            text: 'Cari dan tampilkan template laporan keuangan bulanan yang tersedia di knowledge base.',
            icon: 'monitoring',
            label: 'Cari Template Laporan',
          },
        ].map((btn, idx) => (
          <button key={idx} onClick={() => handleSuggestionClick(btn.text)} className="w-full md:w-auto px-2.5 md:px-4 py-2 md:py-2.5 rounded-2xl bg-surface-container/30 border border-outline-variant/50 hover:border-primary/50 hover:bg-surface-variant transition-all text-[11px] md:text-[13px] text-on-surface-variant hover:text-primary flex items-center justify-center gap-1.5 md:gap-2 group shadow-sm min-w-0">
            <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary transition-colors">{btn.icon}</span>
            <span className="truncate">{btn.label}</span>
          </button>
        ))}
      </div>

      <p className="text-[10px] md:text-[11px] text-outline/60 mt-8 md:mt-12 font-mono text-center max-w-md mx-auto px-4 cursor-default">
        <span className="material-symbols-outlined text-[12px] align-middle mr-1">info</span>
        LapisAI dapat membuat kesalahan. Harap verifikasi informasi penting dengan dokumen sumber.
      </p>
    </div>
  );
};