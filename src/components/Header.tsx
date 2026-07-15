import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

type ChatLanguage = 'ID' | 'EN';

interface HeaderProps {
  isOpen: boolean;
  onToggleSidebar: () => void;
  detectedLanguage: ChatLanguage;
  onLanguageChange: (language: ChatLanguage) => void;
}

const LANGUAGE_OPTIONS: Array<{
  value: ChatLanguage;
  label: string;
  nativeLabel: string;
  description: string;
}> = [
  {
    value: 'ID',
    label: 'Indonesian',
    nativeLabel: 'Bahasa Indonesia',
    description: 'Answer in Indonesian.',
  },
  {
    value: 'EN',
    label: 'English',
    nativeLabel: 'English',
    description: 'Answer in English.',
  },
];

export const Header: React.FC<HeaderProps> = ({
  isOpen,
  onToggleSidebar,
  detectedLanguage,
  onLanguageChange,
}) => {
  const [isLanguageOpen, setIsLanguageOpen] =
    useState(false);

  const languageMenuRef =
    useRef<HTMLDivElement | null>(null);

  const selectedLanguage = useMemo(() => {
    return (
      LANGUAGE_OPTIONS.find(
        (option) => option.value === detectedLanguage
      ) ?? LANGUAGE_OPTIONS[0]
    );
  }, [detectedLanguage]);

  useEffect(() => {
    const handleClickOutside = (
      event: MouseEvent
    ) => {
      if (
        languageMenuRef.current &&
        !languageMenuRef.current.contains(
          event.target as Node
        )
      ) {
        setIsLanguageOpen(false);
      }
    };

    const handleEscape = (
      event: KeyboardEvent
    ) => {
      if (event.key === 'Escape') {
        setIsLanguageOpen(false);
      }
    };

    document.addEventListener(
      'mousedown',
      handleClickOutside
    );
    document.addEventListener(
      'keydown',
      handleEscape
    );

    return () => {
      document.removeEventListener(
        'mousedown',
        handleClickOutside
      );
      document.removeEventListener(
        'keydown',
        handleEscape
      );
    };
  }, []);

  const handleSelectLanguage = (
    language: ChatLanguage
  ) => {
    onLanguageChange(language);
    setIsLanguageOpen(false);
  };

  // --- KODE UPDATE: Class sticky diubah jadi absolute w-full ---
  return (
    <header className="absolute left-0 top-0 w-full z-30 flex h-16 shrink-0 items-center justify-between bg-transparent px-4 md:h-20 md:px-6">
      <button
        type="button"
        onClick={onToggleSidebar}
        className="flex h-12 w-12 items-center justify-center text-white/80 transition-all hover:text-white active:scale-95 md:h-14 md:w-14"
        title={isOpen ? 'Close sidebar' : 'Open sidebar'}
        aria-label={
          isOpen ? 'Close sidebar' : 'Open sidebar'
        }
      >
        {isOpen ? (
          <span className="material-symbols-outlined text-[30px] md:text-[32px]">
            menu_open
          </span>
        ) : (
          <img
            src="/icon.png"
            alt="Open menu"
            className="pointer-events-none h-9 w-9 object-contain md:h-10 md:w-10"
          />
        )}
      </button>

      <div
        ref={languageMenuRef}
        className="relative"
      >
        <button
          type="button"
          onClick={() =>
            setIsLanguageOpen(
              (previousState) => !previousState
            )
          }
          className="
            group flex h-10 min-w-[88px] items-center justify-center gap-2
            rounded-2xl border border-white/10
            bg-white/[0.07] px-2.5
            text-left text-white
            shadow-[0_10px_30px_rgba(0,0,0,0.28)]
            backdrop-blur-xl
            transition-all
            hover:border-primary/40
            hover:bg-white/[0.11]
            focus:border-primary/60
            focus:outline-none
            focus:ring-2
            focus:ring-primary/20
            md:h-11
            md:min-w-[96px]
            md:px-3
          "
          aria-label="Choose chatbot response language"
          aria-expanded={isLanguageOpen}
          aria-haspopup="listbox"
          title={`Language: ${selectedLanguage.nativeLabel}`}
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary md:h-8 md:w-8">
            <span className="material-symbols-outlined text-[18px] md:text-[19px]">
              translate
            </span>
          </span>

          <span className="font-mono text-sm font-bold tracking-[0.08em] text-white md:text-[15px]">
            {selectedLanguage.value}
          </span>

          <span
            className={`
              material-symbols-outlined shrink-0 text-[18px]
              text-white/50 transition-transform
              group-hover:text-white/80
              ${
                isLanguageOpen
                  ? 'rotate-180'
                  : 'rotate-0'
              }
            `}
          >
            expand_more
          </span>
        </button>

        {isLanguageOpen && (
          <div
            className="
              animate-fadeIn absolute right-0 mt-3 w-[230px]
              overflow-hidden rounded-3xl border border-white/10
              bg-[#111111]/95 p-2
              shadow-[0_24px_70px_rgba(0,0,0,0.72)]
              backdrop-blur-2xl
            "
            role="listbox"
            aria-label="Chatbot language list"
          >
            <div className="px-3 pb-2 pt-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">
                Response Language
              </p>
            </div>

            <div className="flex flex-col gap-1">
              {LANGUAGE_OPTIONS.map((option) => {
                const isSelected =
                  option.value === detectedLanguage;

                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() =>
                      handleSelectLanguage(
                        option.value
                      )
                    }
                    className={`
                      flex w-full items-start gap-3 rounded-2xl
                      px-3 py-3 text-left transition-all
                      ${
                        isSelected
                          ? 'bg-primary/15 text-white ring-1 ring-primary/30'
                          : 'text-white/75 hover:bg-white/[0.07] hover:text-white'
                      }
                    `}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <span
                      className={`
                        mt-0.5 flex h-8 w-8 shrink-0 items-center
                        justify-center rounded-xl font-mono text-xs font-bold
                        ${
                          isSelected
                            ? 'bg-primary text-black'
                            : 'bg-white/10 text-white/70'
                        }
                      `}
                    >
                      {option.value}
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold">
                        {option.label}
                      </span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-white/45">
                        {option.description}
                      </span>
                    </span>

                    {isSelected && (
                      <span className="material-symbols-outlined mt-1 text-[18px] text-primary">
                        check_circle
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;