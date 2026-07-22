import React, { useEffect, useRef, useState } from 'react';
import { AttachedFile } from '../types';
import type { ModelType } from '../types';

type UploadMode = 'photo' | 'file';
type ChatLanguage = 'ID' | 'EN';


const MODEL_OPTIONS: Array<{
  value: ModelType;
  label: string;
  icon: string;
}> = [
  { value: 'ollama', label: 'Ollama (Local)', icon: 'memory' },
  { value: 'gemini', label: 'Gemini', icon: 'cloud' },
  { value: 'groq', label: 'Groq Cloud', icon: 'bolt' },
];

interface WelcomeScreenProps {
  onSendMessage: (text: string, files: AttachedFile[]) => void;
  onAttachFileClick: (mode: UploadMode) => void;
  onMicClick: () => void;
  language?: ChatLanguage;
  model: ModelType;
  onModelChange: (model: ModelType) => void;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  onSendMessage,
  onMicClick,
  language = 'ID',
  model,
  onModelChange,
}) => {
  const [inputValue, setInputValue] = useState('');
  
  // State untuk menu
  const [modelMenuOpen, setModelMenuOpen] = useState(false);

  const [placeholder, setPlaceholder] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const placeholdersData = {
    ID: ['Tanyakan apa saja...', 'Berapa lama masa percobaan?', 'Cek SLA insiden IT...'],
    EN: ['Ask anything...', 'How long is probation?', 'Check IT incident SLA...'],
  };

  useEffect(() => {
    const currentPlaceholders = placeholdersData[language];
    let placeholderIndex = 0;
    let characterIndex = 0;
    let isDeleting = false;
    let timer: ReturnType<typeof setTimeout>;

    const typePlaceholder = () => {
      if (document.activeElement === textareaRef.current || inputValue !== '') {
        return;
      }

      const currentText = currentPlaceholders[placeholderIndex];

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
        placeholderIndex = (placeholderIndex + 1) % currentPlaceholders.length;
        typingSpeed = 500;
      }

      timer = setTimeout(typePlaceholder, typingSpeed);
    };

    timer = setTimeout(typePlaceholder, 500);

    return () => clearTimeout(timer);
  }, [inputValue, language]);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    onSendMessage(inputValue, []);
    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // Reset height setelah kirim
    }
  };

  const handleSuggestionClick = (text: string) => {
    setInputValue(text);
    if (textareaRef.current) {
      textareaRef.current.focus();
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
          textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
        }
      }, 0);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  // --- KODE UPDATE: Data Rekomendasi dari ground_truth_qa.csv ---
  const suggestions = [
    {
      icon: 'badge',
      title: { ID: 'Masa Percobaan', EN: 'Probation Period' },
      desc: { ID: 'Aturan karyawan baru', EN: 'New employee rules' },
      text: { 
        ID: 'Berapa lama masa percobaan untuk karyawan baru?', 
        EN: 'How long is the probation period for new employees?' 
      },
    },
    {
      icon: 'support_agent',
      title: { ID: 'Insiden IT', EN: 'IT Incident' },
      desc: { ID: 'SLA penanganan prioritas P1', EN: 'P1 priority handling SLA' },
      text: { 
        ID: 'Seberapa cepat insiden IT P1 harus diselesaikan?', 
        EN: 'How quickly must a P1 IT incident be resolved?' 
      },
    },
    {
      icon: 'account_balance_wallet',
      title: { ID: 'Persetujuan Dana', EN: 'Fund Approval' },
      desc: { ID: 'Syarat untuk >Rp 50 Juta', EN: 'Requirements for >50M' },
      text: { 
        ID: 'Persetujuan apa yang diperlukan untuk pembelian di atas Rp 50 juta?', 
        EN: 'What approval is needed for a purchase above IDR 50 million?' 
      },
    }
  ];

  return (
    <div className="relative flex-1 min-h-full w-full overflow-hidden">
      
      {/* CSS Animasi Khusus untuk Border Gradient */}
      <style>{`
        @keyframes gradient-border {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        .animate-gradient-border {
          background-size: 300% 300%;
          animation: gradient-border 4s ease infinite;
        }
      `}</style>

      {/* Background Avatar */}
      <div className="absolute left-0 top-0 h-full w-full md:w-[40%] lg:w-[35%] max-w-[500px] z-0 pointer-events-none">
        <img
          src="/icon-orang.png" 
          alt="Lapis AI Avatar"
          className="h-full w-full object-cover object-left opacity-30 mix-blend-screen [mask-image:linear-gradient(to_right,rgba(0,0,0,1)_30%,rgba(0,0,0,0)_90%)] [-webkit-mask-image:linear-gradient(to_right,rgba(0,0,0,1)_30%,rgba(0,0,0,0)_90%)]" 
        />
      </div>

      <div className="relative z-10 flex min-h-full w-full items-center justify-center px-4 pb-6 pt-20 sm:px-6 md:px-8 md:pt-6">
        <div className="flex w-full max-w-3xl flex-col items-center justify-center translate-y-8 md:translate-y-12 lg:translate-y-16 animate-fadeIn">
          
          <h1 className="mb-7 max-w-[340px] text-center font-headline text-[27px] font-medium leading-[1.16] tracking-tight text-on-surface sm:max-w-xl sm:text-3xl md:mb-8 md:max-w-none md:text-4xl">
            {language === 'ID' ? 'Ada yang bisa saya bantu?' : 'How can I help you?'}
          </h1>

          {/* Kotak Input Utama */}
          <div className="relative w-full max-w-[760px] px-1 md:px-2">
            {/* EFEK CAHAYA (BLOBS) DITERANGKAN: Opacity dinaikkan menjadi /60 dan /70 */}
            <div className="pointer-events-none absolute -left-4 top-1/2 z-0 h-28 w-40 -translate-y-1/2 rounded-full bg-[#fb7185]/60 blur-[40px] md:-left-10 md:h-36 md:w-52 md:blur-[50px]" />
            <div className="pointer-events-none absolute -right-4 top-1/2 z-0 h-28 w-40 -translate-y-1/2 rounded-full bg-[#3b82f6]/70 blur-[40px] md:-right-10 md:h-36 md:w-52 md:blur-[50px]" />

            {/* DIV BORDER: Garis tetap soft (rgba), tapi shadow luar diubah jadi glow terang (rgba ungu) */}
            <div className="relative z-10 rounded-[24px] bg-[linear-gradient(90deg,rgba(251,113,133,0.5),rgba(139,92,246,0.4),rgba(59,130,246,0.5),rgba(251,113,133,0.5))] p-[1.5px] shadow-[0_0_30px_rgba(139,92,246,0.25)] transition-all duration-300 focus-within:shadow-[0_0_40px_rgba(139,92,246,0.45)] md:rounded-[28px] animate-gradient-border">
              <div className="relative flex flex-col w-full rounded-[22.5px] bg-[#111216] md:rounded-[26.5px] p-2 md:p-3">
                
                <textarea
                  ref={textareaRef}
                  className="w-full bg-transparent border-none py-2 px-2 text-[15px] text-white/90 outline-none placeholder:text-white/40 focus:ring-0 resize-none min-h-[70px] md:min-h-[80px] custom-scrollbar"
                  placeholder={placeholder}
                  value={inputValue}
                  onChange={handleInput}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      handleSend();
                    }
                  }}
                  onFocus={() => setPlaceholder(language === 'ID' ? 'Tanyakan apa saja...' : 'Ask anything...')}
                />

                <div className="flex w-full items-center justify-between mt-1 pt-1">
                  
                  {/* Grup Kiri */}
                  <div className="flex items-center gap-2">
                    <div className="relative hidden sm:block">
                      <button
                        type="button"
                        onClick={() => setModelMenuOpen(!modelMenuOpen)}
                        className="flex items-center gap-1.5 h-9 px-3.5 rounded-full bg-white/5 border border-white/10 text-white/60 transition-all hover:bg-white/10 hover:text-white"
                      >
                        <span className="material-symbols-outlined text-[16px]">energy_savings_leaf</span>
                        <span className="text-[13px] font-medium">{MODEL_OPTIONS.find((option) => option.value === model)?.label ?? model}</span>
                        <span className="material-symbols-outlined text-[16px]">expand_more</span>
                      </button>

                      {modelMenuOpen && (
                        <div className="absolute top-full left-0 z-30 mt-5 w-44 rounded-2xl border border-white/10 bg-[#1a1b21] p-2 shadow-xl animate-fadeIn">
                          {MODEL_OPTIONS.map((option) => (
                            <button
                              key={option.value}
                              onClick={() => {
                                onModelChange(option.value);
                                setModelMenuOpen(false);
                              }}
                              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${model === option.value ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5'}`}
                            >
                              <span className="material-symbols-outlined text-[16px]">{option.icon}</span> {option.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Grup Kanan */}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={onMicClick}
                      className="flex items-center gap-1.5 h-9 px-3.5 rounded-full bg-white/5 border border-white/10 text-white/60 transition-all hover:bg-white/10 hover:text-white"
                    >
                      <span className="material-symbols-outlined text-[16px]">graphic_eq</span>
                      <span className="text-[13px] font-medium hidden sm:block">Voice</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleSend}
                      className="flex h-9 w-9 items-center justify-center rounded-full bg-[linear-gradient(135deg,#a855f7_0%,#ec4899_100%)] text-white shadow-lg transition-all hover:scale-105 active:scale-95"
                    >
                      <span className="material-symbols-outlined icon-filled text-[18px]">send</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Kartu Rekomendasi */}
          <div className="mt-8 w-full max-w-[720px] px-1 md:px-0 animate-fadeIn">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4">
              {suggestions.map((card, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSuggestionClick(card.text[language])}
                  className="flex flex-col text-left p-4 md:p-5 rounded-[20px] bg-[#1a1b21] hover:bg-[#22232b] transition-all active:scale-[0.98] group"
                >
                  <span className="material-symbols-outlined text-[22px] text-white/70 mb-3 group-hover:text-white transition-colors">
                    {card.icon}
                  </span>
                  <div className="text-[14px] md:text-[15px] font-semibold text-white/90 mb-1 leading-tight">
                    {card.title[language]}
                  </div>
                  <div className="text-[12px] md:text-[13px] text-white/40 leading-snug">
                    {card.desc[language]}
                  </div>
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;