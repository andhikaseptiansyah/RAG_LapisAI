import React, { useEffect, useRef, useState } from 'react';
import { AttachedFile } from '../types';

type UploadMode = 'photo' | 'file';

interface WelcomeScreenProps {
  onSendMessage: (text: string, files: AttachedFile[]) => void;
  onAttachFileClick: (mode: UploadMode) => void;
  onMicClick: () => void;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  onSendMessage,
  onAttachFileClick,
  onMicClick,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);
  const [placeholder, setPlaceholder] = useState('Minta Assistant...');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const placeholders = [
      'Lapis AI Assistant...',
      'Minta Assistant...',
      'Cari SOP Klaim Medis...',
      'Bantu saya menganalisis data...',
      'Tampilkan Kebijakan WFH...',
    ];

    let placeholderIndex = 0;
    let characterIndex = 0;
    let isDeleting = false;
    let timer: ReturnType<typeof setTimeout>;

    const typePlaceholder = () => {
      if (document.activeElement === inputRef.current || inputValue !== '') {
        return;
      }

      const currentText = placeholders[placeholderIndex];

      if (isDeleting) {
        setPlaceholder(currentText.substring(0, characterIndex - 1));
        characterIndex--;
      } else {
        setPlaceholder(currentText.substring(0, characterIndex + 1));
        characterIndex++;
      }

      let typingSpeed = isDeleting ? 30 : 70;

      if (!isDeleting && characterIndex === currentText.length) {
        typingSpeed = 2000;
        isDeleting = true;
      } else if (isDeleting && characterIndex === 0) {
        isDeleting = false;
        placeholderIndex = (placeholderIndex + 1) % placeholders.length;
        typingSpeed = 500;
      }

      timer = setTimeout(typePlaceholder, typingSpeed);
    };

    timer = setTimeout(typePlaceholder, 500);

    return () => clearTimeout(timer);
  }, [inputValue]);

  const handleSend = () => {
    if (!inputValue.trim()) return;

    onSendMessage(inputValue, []);
    setInputValue('');
  };

  const handleSuggestionClick = (text: string) => {
    onSendMessage(text, []);
  };

  const handleUploadOptionClick = (mode: UploadMode) => {
    setAttachMenuOpen(false);
    onAttachFileClick(mode);
  };

  const suggestions = [
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
  ];

  return (
    <div className="relative flex-1 min-h-full w-full overflow-hidden">
      <div className="relative z-10 flex min-h-full w-full items-center justify-center px-4 py-6 sm:px-6 md:px-8">
        <div className="flex w-full max-w-3xl flex-col items-center justify-center -mt-4 md:-mt-16 animate-fadeIn">
          {/* Logo Tengah */}
          <div className="mb-5 flex items-center justify-center animate-[pulse_3s_ease-in-out_infinite] md:mb-6">
            <img
              src="/icon-ungu.png"
              alt="Lapis Logo"
              className="w-20 h-auto object-contain sm:w-24 md:w-32"
            />
          </div>

          {/* Judul */}
          <h1 className="mb-7 max-w-[340px] text-center font-headline text-[27px] font-medium leading-[1.16] tracking-tight text-on-surface sm:max-w-xl sm:text-3xl md:mb-8 md:max-w-none md:text-4xl">
            Apa yang bisa saya bantu, Staff User?
          </h1>

          {/* Input Chat */}
          <div className="relative flex min-h-[58px] w-full max-w-[700px] items-center rounded-[26px] border border-white/5 bg-welcome-gradient shadow-[0_10px_32px_rgba(0,0,0,0.28)] transition-all duration-300 hover:brightness-110 focus-within:border-outline-variant/40 focus-within:brightness-110 md:min-h-[64px] md:rounded-[32px]">
            <input
              ref={inputRef}
              type="text"
              className="w-full rounded-[26px] border-none bg-transparent py-4 pl-[62px] pr-[94px] text-[15px] text-on-surface outline-none placeholder:text-on-surface-variant/70 focus:ring-0 sm:pl-[68px] md:rounded-[32px] md:py-4 md:pl-[72px] md:pr-[100px] md:text-[17px]"
              placeholder={placeholder}
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && handleSend()}
              onFocus={() => setPlaceholder('Ketik sesuatu...')}
            />

            {/* Tombol + */}
            <div className="absolute left-2 flex items-center">
              <div className="relative">
                <button
                  type="button"
                  onClick={() =>
                    setAttachMenuOpen((previous) => !previous)
                  }
                  className="flex h-9 w-9 items-center justify-center rounded-full text-outline transition-colors hover:bg-surface-variant hover:text-primary md:h-10 md:w-10"
                  title="Tambah lampiran"
                >
                  <span className="material-symbols-outlined text-[21px] md:text-[22px]">
                    add
                  </span>
                </button>

                {attachMenuOpen && (
                  <div className="absolute bottom-full left-0 z-20 mb-3 w-52 rounded-2xl border border-outline-variant bg-surface-container-high p-2 shadow-[0_14px_40px_rgba(0,0,0,0.5)] animate-fadeIn">
                    <button
                      type="button"
                      onClick={() => handleUploadOptionClick('photo')}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm text-on-surface-variant transition-colors hover:bg-surface-container hover:text-primary"
                    >
                      <span className="material-symbols-outlined text-[20px]">
                        add_photo_alternate
                      </span>
                      Upload Foto
                    </button>

                    <button
                      type="button"
                      onClick={() => handleUploadOptionClick('file')}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm text-on-surface-variant transition-colors hover:bg-surface-container hover:text-primary"
                    >
                      <span className="material-symbols-outlined text-[20px]">
                        description
                      </span>
                      Upload File
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Tombol Mic dan Send */}
            <div className="absolute right-2 flex items-center gap-1">
              <button
                type="button"
                onClick={onMicClick}
                className="flex h-9 w-9 items-center justify-center rounded-full text-outline transition-colors hover:bg-surface-variant hover:text-primary md:h-10 md:w-10"
                title="Voice to Text"
              >
                <span
                  className="flex h-5 w-5 items-center justify-center gap-[2px]"
                  aria-hidden="true"
                >
                  <span className="h-2.5 w-[2px] rounded-full bg-current" />
                  <span className="h-4 w-[2px] rounded-full bg-current" />
                  <span className="h-5 w-[2px] rounded-full bg-current" />
                  <span className="h-4 w-[2px] rounded-full bg-current" />
                  <span className="h-2.5 w-[2px] rounded-full bg-current" />
                </span>
              </button>

              <button
                type="button"
                onClick={handleSend}
                className="ml-1 flex h-10 w-10 items-center justify-center rounded-full bg-primary text-on-primary-container shadow-sm transition-all hover:bg-primary-container active:scale-95 md:h-11 md:w-11"
                title="Kirim pesan"
              >
                <span className="material-symbols-outlined icon-filled text-[21px] md:text-[22px]">
                  send
                </span>
              </button>
            </div>
          </div>

          {/* Suggestion Button */}
          <div className="mt-6 w-full max-w-[700px] animate-[fadeIn_0.7s_ease-out]">
            <div className="grid grid-cols-2 gap-2 md:flex md:flex-wrap md:justify-center md:gap-3">
              {suggestions.map((button) => (
                <button
                  key={button.label}
                  type="button"
                  onClick={() => handleSuggestionClick(button.text)}
                  className="group flex min-w-0 w-full items-center justify-center gap-1.5 rounded-2xl border border-outline-variant/50 bg-surface-container/25 px-2.5 py-2 text-[10px] text-on-surface-variant shadow-sm transition-all hover:border-primary/50 hover:bg-surface-variant hover:text-primary md:w-auto md:gap-2 md:px-4 md:py-2.5 md:text-[13px]"
                >
                  <span className="material-symbols-outlined shrink-0 text-[15px] text-outline transition-colors group-hover:text-primary md:text-[16px]">
                    {button.icon}
                  </span>

                  <span className="truncate whitespace-nowrap">
                    {button.label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Disclaimer */}
          <p className="mx-auto mt-7 max-w-[325px] px-3 text-center font-mono text-[10px] leading-relaxed text-outline/60 sm:max-w-md md:mt-12 md:max-w-md md:px-4 md:text-[11px]">
            <span className="material-symbols-outlined mr-1 align-middle text-[12px]">
              info
            </span>
            LapisAI dapat membuat kesalahan. Harap verifikasi informasi penting
            dengan dokumen sumber.
          </p>
        </div>
      </div>
    </div>
  );
};