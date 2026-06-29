import React, { useEffect, useMemo, useState } from 'react';

export interface ConversationHistory {
  id: string;
  title: string;
  dateLabel: string;
  group: string;
  pinned?: boolean;
}

interface ConversationSearchProps {
  conversations: ConversationHistory[];
  onSelectConversation: (
    conversation: ConversationHistory
  ) => void;
  onBack: () => void;
  sidebarVisible?: boolean;
}

export const ConversationSearch: React.FC<
  ConversationSearchProps
> = ({
  conversations,
  onSelectConversation,
  onBack,
  sidebarVisible = true,
}) => {
  const [searchKeyword, setSearchKeyword] =
    useState('');

  useEffect(() => {
    const handleEscape = (
      event: KeyboardEvent
    ) => {
      if (event.key === 'Escape') {
        onBack();
      }
    };

    window.addEventListener(
      'keydown',
      handleEscape
    );

    return () => {
      window.removeEventListener(
        'keydown',
        handleEscape
      );
    };
  }, [onBack]);

  const filteredConversations = useMemo(() => {
    const keyword = searchKeyword
      .trim()
      .toLowerCase();

    if (!keyword) {
      return conversations;
    }

    return conversations.filter(
      (conversation) =>
        conversation.title
          .toLowerCase()
          .includes(keyword)
    );
  }, [conversations, searchKeyword]);

  return (
    <section
      className={`
        fixed inset-y-0 right-0
        z-[60] md:z-40
        overflow-hidden
        border-l border-white/10
        font-body text-white
        transition-[left] duration-300
        ${
          sidebarVisible
            ? 'left-0 md:left-64'
            : 'left-0'
        }
      `}
      style={{
        background:
          'radial-gradient(circle at 50% 42%, rgba(43, 78, 170, 0.24) 0%, rgba(16, 27, 72, 0.14) 30%, rgba(0, 0, 0, 0) 64%), linear-gradient(180deg, #000000 0%, #010208 52%, #000000 100%)',
      }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at center, rgba(91, 132, 255, 0.08) 0%, rgba(0, 0, 0, 0) 54%)',
        }}
      />

      <div className="relative z-10 flex h-full min-h-0 flex-col">
        {/* Bagian atas tetap diam */}
        <div className="shrink-0 px-4 pt-5 sm:px-6 md:px-10 md:pt-8 lg:px-14">
          <div className="mx-auto w-full max-w-5xl">
            {/* Search bar */}
            <div className="mb-7 md:mb-8">
              <div className="relative">
                <span className="material-symbols-outlined pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[23px] text-white/55 md:left-6 md:text-[25px]">
                  search
                </span>

                <input
                  type="text"
                  value={searchKeyword}
                  onChange={(event) =>
                    setSearchKeyword(
                      event.target.value
                    )
                  }
                  placeholder="Telusuri percakapan"
                  autoFocus
                  className="
                    h-14 w-full
                    rounded-2xl
                    border border-white/10
                    bg-[rgba(27,29,38,0.90)]
                    py-3 pl-14 pr-14
                    text-[15px]
                    text-white
                    outline-none
                    shadow-[0_14px_40px_rgba(0,0,0,0.34)]
                    backdrop-blur-md
                    placeholder:text-white/40
                    transition-all
                    focus:border-primary/70
                    focus:ring-1
                    focus:ring-primary/40
                    md:h-16
                    md:rounded-3xl
                    md:pl-16
                    md:pr-16
                    md:text-[17px]
                  "
                />

                {searchKeyword ? (
                  <button
                    type="button"
                    onClick={() =>
                      setSearchKeyword('')
                    }
                    className="
                      absolute right-3 top-1/2
                      flex h-9 w-9
                      -translate-y-1/2
                      items-center justify-center
                      rounded-full
                      text-white/45
                      transition-colors
                      hover:bg-white/5
                      hover:text-white
                      md:right-4
                    "
                    aria-label="Hapus pencarian"
                    title="Hapus pencarian"
                  >
                    <span className="material-symbols-outlined text-[20px]">
                      close
                    </span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={onBack}
                    className="
                      absolute right-3 top-1/2
                      flex h-9 w-9
                      -translate-y-1/2
                      items-center justify-center
                      rounded-full
                      text-white/45
                      transition-colors
                      hover:bg-white/5
                      hover:text-white
                      md:right-4
                    "
                    aria-label="Tutup pencarian"
                    title="Tutup pencarian"
                  >
                    <span className="material-symbols-outlined text-[20px]">
                      close
                    </span>
                  </button>
                )}
              </div>
            </div>

            {/* Header history tetap diam */}
            <div className="mb-4 flex items-center justify-between gap-4 px-1 md:px-2">
              <div className="min-w-0">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/35">
                  Conversation History
                </p>

                <h1 className="mt-1 truncate font-headline text-lg font-semibold text-white md:text-xl">
                  {searchKeyword
                    ? 'Hasil Pencarian'
                    : 'Terbaru'}
                </h1>
              </div>

              <span className="shrink-0 rounded-full border border-white/10 bg-[rgba(21,23,32,0.80)] px-3 py-1.5 font-mono text-[10px] text-white/50 backdrop-blur-md md:text-xs">
                {filteredConversations.length}{' '}
                percakapan
              </span>
            </div>
          </div>
        </div>

        {/* Hanya daftar history yang bisa di-scroll */}
        <div className="min-h-0 flex-1 px-4 pb-8 sm:px-6 md:px-10 lg:px-14">
          <div className="mx-auto h-full w-full max-w-5xl overflow-hidden rounded-2xl border border-white/10 bg-[rgba(17,19,26,0.78)] shadow-[0_18px_50px_rgba(0,0,0,0.35)] backdrop-blur-md">
            <div className="custom-scrollbar h-full overflow-y-auto overscroll-contain">
              {filteredConversations.length >
              0 ? (
                <div className="divide-y divide-white/[0.07]">
                  {filteredConversations.map(
                    (conversation) => (
                      <button
                        key={conversation.id}
                        type="button"
                        onClick={() =>
                          onSelectConversation(
                            conversation
                          )
                        }
                        className="
                          group
                          flex w-full
                          items-center
                          justify-between
                          gap-5
                          px-4 py-4
                          text-left
                          transition-colors
                          hover:bg-white/[0.04]
                          sm:px-5
                          md:px-6
                        "
                      >
                        <div className="flex min-w-0 flex-1 items-center gap-3">
                          <span className="material-symbols-outlined shrink-0 text-[18px] text-white/40 transition-colors group-hover:text-primary">
                            chat_bubble
                          </span>

                          <p className="truncate text-[14px] font-medium text-white/[0.85] transition-colors group-hover:text-primary md:text-[16px]">
                            {conversation.title}
                          </p>

                          {conversation.pinned && (
                            <span
                              className="material-symbols-outlined shrink-0 text-[15px] text-primary"
                              title="Percakapan disematkan"
                            >
                              push_pin
                            </span>
                          )}
                        </div>

                        <span className="w-[78px] shrink-0 text-right font-mono text-[10px] text-white/35 md:w-[100px] md:text-xs">
                          {conversation.dateLabel}
                        </span>
                      </button>
                    )
                  )}
                </div>
              ) : (
                <div className="flex h-full min-h-[260px] flex-col items-center justify-center px-6 text-center">
                  <span className="material-symbols-outlined mb-3 text-[42px] text-white/20">
                    search_off
                  </span>

                  <p className="font-headline text-base font-semibold text-white/80">
                    Percakapan tidak ditemukan
                  </p>

                  <p className="mt-1 text-sm text-white/35">
                    Coba gunakan kata kunci lain.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};