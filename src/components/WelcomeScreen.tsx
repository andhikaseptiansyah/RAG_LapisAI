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
  const [placeholder, setPlaceholder] = useState('Tanyakan isi dokumen perusahaan...');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const placeholders = [
      'Tanyakan isi dokumen perusahaan...',
      'Cari prosedur reset password...',
      'Cek reimbursement untuk kebutuhan WFH...',
      'Lihat laporan keuangan FY2025...',
      'Cari panduan VPN perusahaan...',
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
      text: 'Jika saya lupa password untuk masuk ke sistem internal, apa prosedur reset yang harus dilakukan dan berapa lama maksimal prosesnya?',
      icon: 'password',
      label: 'Reset Password IT',
    },
    {
      text: 'Jika saya membeli meja ergonomis seharga Rp2.000.000 untuk kebutuhan WFH, berapa maksimal reimbursement dari perusahaan dan apakah nota asli wajib dilampirkan?',
      icon: 'home_work',
      label: 'Reimbursement WFH',
    },
    {
      text: 'Berapa total pendapatan perusahaan sepanjang FY2025 dan berapa persentase margin laba bersihnya?',
      icon: 'monitoring',
      label: 'Laporan Finansial 2025',
    },
    {
      text: 'Perangkat lunak VPN apa yang wajib digunakan untuk mengakses jaringan perusahaan, dan lapisan keamanan tambahan apa yang diaktifkan saat login?',
      icon: 'vpn_lock',
      label: 'Panduan VPN',
    },
  ];

  return (
    <div className="relative flex-1 min-h-full w-full overflow-hidden">
      <div className="relative z-10 flex min-h-full w-full items-center justify-center px-4 py-6 sm:px-6 md:px-8">
        <div className="flex w-full max-w-3xl flex-col items-center justify-center -mt-4 md:-mt-16 animate-fadeIn">
          {/* Center Logo */}
          <div className="mb-5 flex items-center justify-center animate-[pulse_3s_ease-in-out_infinite] md:mb-6">
            <img
              src="/icon-ungu.png"
              alt="Lapis Logo"
              className="w-20 h-auto object-contain sm:w-24 md:w-32"
            />
          </div>

          {/* Title */}
          <h1 className="mb-7 max-w-[340px] text-center font-headline text-[27px] font-medium leading-[1.16] tracking-tight text-on-surface sm:max-w-xl sm:text-3xl md:mb-8 md:max-w-none md:text-4xl">
            How can I help you, Staff ?
          </h1>

          {/* Chat Input Glow */}
          <div className="relative w-full max-w-[760px] px-1 md:px-2">
            {/* Softer and more balanced glow */}
            <div className="pointer-events-none absolute -left-4 top-1/2 z-0 h-28 w-40 -translate-y-1/2 rounded-full bg-[#fb7185]/35 blur-[44px] md:-left-10 md:h-36 md:w-52 md:blur-[56px]" />
            <div className="pointer-events-none absolute -right-4 top-1/2 z-0 h-28 w-40 -translate-y-1/2 rounded-full bg-[#3b82f6]/45 blur-[44px] md:-right-10 md:h-36 md:w-52 md:blur-[56px]" />
            <div className="pointer-events-none absolute left-1/2 top-1/2 z-0 h-16 w-[62%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#8b5cf6]/18 blur-[38px]" />

            {/* Clean gradient border */}
            <div className="relative z-10 rounded-[28px] bg-[linear-gradient(90deg,rgba(251,113,133,0.75)_0%,rgba(139,92,246,0.55)_46%,rgba(59,130,246,0.85)_100%)] p-[1.3px] shadow-[0_0_22px_rgba(251,113,133,0.18),0_0_30px_rgba(59,130,246,0.24)] transition-all duration-300 focus-within:shadow-[0_0_30px_rgba(251,113,133,0.26),0_0_42px_rgba(59,130,246,0.32)] md:rounded-[34px]">
              <div className="relative flex min-h-[58px] w-full items-center overflow-visible rounded-[26.5px] bg-[linear-gradient(180deg,rgba(16,18,28,0.98),rgba(7,9,16,0.98))] shadow-[inset_0_1px_0_rgba(255,255,255,0.08),inset_0_-1px_0_rgba(255,255,255,0.04)] md:min-h-[64px] md:rounded-[32.5px]">
                <div className="pointer-events-none absolute inset-0 rounded-[26.5px] bg-[radial-gradient(circle_at_0%_50%,rgba(251,113,133,0.16),transparent_34%),radial-gradient(circle_at_100%_50%,rgba(59,130,246,0.18),transparent_34%)] md:rounded-[32.5px]" />

                <input
                  ref={inputRef}
                  type="text"
                  className="relative z-10 w-full rounded-[26px] border-none bg-transparent py-4 pl-[62px] pr-[94px] text-[15px] text-on-surface outline-none placeholder:text-on-surface-variant/70 focus:ring-0 sm:pl-[68px] md:rounded-[32px] md:py-4 md:pl-[72px] md:pr-[100px] md:text-[17px]"
                  placeholder={placeholder}
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  onKeyDown={(event) => event.key === 'Enter' && handleSend()}
                  onFocus={() => setPlaceholder('Type something...')}
                />

                {/* Add Button */}
                <div className="absolute left-2 z-20 flex items-center">
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setAttachMenuOpen((previous) => !previous)}
                      className="flex h-9 w-9 items-center justify-center rounded-full border border-white/25 bg-white/[0.04] text-outline transition-all hover:border-cyan-300/50 hover:bg-white/[0.08] hover:text-cyan-300 md:h-10 md:w-10"
                      title="Add attachment"
                    >
                      <span className="material-symbols-outlined text-[21px] md:text-[22px]">
                        add
                      </span>
                    </button>

                    {attachMenuOpen && (
                      <div className="absolute bottom-full left-0 z-30 mb-3 w-52 rounded-2xl border border-outline-variant bg-surface-container-high p-2 shadow-[0_14px_40px_rgba(0,0,0,0.5)] animate-fadeIn">
                        <button
                          type="button"
                          onClick={() => handleUploadOptionClick('photo')}
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm text-on-surface-variant transition-colors hover:bg-surface-container hover:text-primary"
                        >
                          <span className="material-symbols-outlined text-[20px]">
                            add_photo_alternate
                          </span>
                          Upload Photo
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

                {/* Mic and Send Buttons */}
                <div className="absolute right-2 z-20 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={onMicClick}
                    className="flex h-9 w-9 items-center justify-center rounded-full border border-white/25 bg-white/[0.04] text-outline transition-all hover:border-blue-300/50 hover:bg-white/[0.08] hover:text-blue-300 md:h-10 md:w-10"
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
                    className="ml-1 flex h-10 w-10 items-center justify-center rounded-full bg-[linear-gradient(135deg,#dbeafe_0%,#93c5fd_45%,#a78bfa_100%)] text-slate-900 shadow-[0_0_18px_rgba(147,197,253,0.45)] transition-all hover:scale-[1.03] hover:shadow-[0_0_28px_rgba(167,139,250,0.52)] active:scale-95 md:h-11 md:w-11"
                    title="Send message"
                  >
                    <span className="material-symbols-outlined icon-filled text-[21px] md:text-[22px]">
                      send
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Suggestion Buttons */}
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
            LapisAI may make mistakes. Please verify important information with the source documents.
          </p>
        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;
