import React, { useEffect, useMemo, useState } from 'react';

export interface ConversationQuestion {
  id: string;
  content: string;
  dateLabel: string;
  createdAt?: string;
}

export interface ConversationHistory {
  id: string;
  title: string;
  dateLabel: string;
  group: string;
  pinned?: boolean;
  questions: ConversationQuestion[];
}

interface ConversationSearchProps {
  conversations: ConversationHistory[];
  onSelectConversation: (
    conversation: ConversationHistory,
    targetMessageId?: string
  ) => void;
  onDeleteConversations: (
    conversationIds: string[]
  ) => Promise<void>;
  onBack: () => void;
  sidebarVisible?: boolean;
}

export const ConversationSearch: React.FC<
  ConversationSearchProps
> = ({
  conversations,
  onSelectConversation,
  onDeleteConversations,
  onBack,
  sidebarVisible = true,
}) => {
  const [searchKeyword, setSearchKeyword] =
    useState('');
  const [isSelectionMode, setIsSelectionMode] =
    useState(false);
  const [selectedConversationIds, setSelectedConversationIds] =
    useState<Set<string>>(() => new Set());
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] =
    useState(false);
  const [isDeleting, setIsDeleting] =
    useState(false);
  const [deleteError, setDeleteError] =
    useState<string | null>(null);

  const filteredConversations = useMemo(() => {
    const keyword = searchKeyword
      .trim()
      .toLocaleLowerCase();

    if (!keyword) {
      return conversations;
    }

    return conversations
      .map((conversation) => {
        const titleMatches = conversation.title
          .toLocaleLowerCase()
          .includes(keyword);
        const matchingQuestions =
          conversation.questions.filter((question) =>
            question.content
              .toLocaleLowerCase()
              .includes(keyword)
          );

        if (!titleMatches && matchingQuestions.length === 0) {
          return null;
        }

        return {
          ...conversation,
          questions: titleMatches
            ? conversation.questions
            : matchingQuestions,
        };
      })
      .filter(
        (
          conversation
        ): conversation is ConversationHistory =>
          conversation !== null
      );
  }, [conversations, searchKeyword]);

  const filteredConversationIds = useMemo(
    () =>
      filteredConversations.map(
        (conversation) => conversation.id
      ),
    [filteredConversations]
  );

  const questionCount = useMemo(
    () =>
      filteredConversations.reduce(
        (total, conversation) =>
          total + Math.max(conversation.questions.length, 1),
        0
      ),
    [filteredConversations]
  );

  const selectedCount = selectedConversationIds.size;

  const allFilteredSelected =
    filteredConversationIds.length > 0 &&
    filteredConversationIds.every((conversationId) =>
      selectedConversationIds.has(conversationId)
    );

  useEffect(() => {
    const availableIds = new Set(
      conversations.map((conversation) => conversation.id)
    );

    setSelectedConversationIds((previousIds) => {
      const nextIds = new Set(
        Array.from(previousIds).filter((conversationId) =>
          availableIds.has(conversationId)
        )
      );

      return nextIds.size === previousIds.size
        ? previousIds
        : nextIds;
    });
  }, [conversations]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || isDeleting) {
        return;
      }

      if (isDeleteConfirmOpen) {
        setIsDeleteConfirmOpen(false);
        setDeleteError(null);
        return;
      }

      if (isSelectionMode) {
        setIsSelectionMode(false);
        setSelectedConversationIds(new Set());
        return;
      }

      onBack();
    };

    window.addEventListener('keydown', handleEscape);

    return () => {
      window.removeEventListener('keydown', handleEscape);
    };
  }, [
    isDeleteConfirmOpen,
    isDeleting,
    isSelectionMode,
    onBack,
  ]);

  const toggleConversationSelection = (
    conversationId: string
  ): void => {
    setSelectedConversationIds((previousIds) => {
      const nextIds = new Set(previousIds);

      if (nextIds.has(conversationId)) {
        nextIds.delete(conversationId);
      } else {
        nextIds.add(conversationId);
      }

      return nextIds;
    });
  };

  const toggleSelectAllFiltered = (): void => {
    setSelectedConversationIds((previousIds) => {
      const nextIds = new Set(previousIds);

      filteredConversationIds.forEach((conversationId) => {
        if (allFilteredSelected) {
          nextIds.delete(conversationId);
        } else {
          nextIds.add(conversationId);
        }
      });

      return nextIds;
    });
  };

  const handleQuestionClick = (
    conversation: ConversationHistory,
    targetMessageId?: string
  ): void => {
    if (isSelectionMode) {
      toggleConversationSelection(conversation.id);
      return;
    }

    onSelectConversation(conversation, targetMessageId);
  };

  const exitSelectionMode = (): void => {
    if (isDeleting) {
      return;
    }

    setIsSelectionMode(false);
    setSelectedConversationIds(new Set());
    setIsDeleteConfirmOpen(false);
    setDeleteError(null);
  };

  const confirmDeleteSelected = async (): Promise<void> => {
    const conversationIds = Array.from(
      selectedConversationIds
    );

    if (conversationIds.length === 0) {
      setIsDeleteConfirmOpen(false);
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await onDeleteConversations(conversationIds);
      exitSelectionMode();
    } catch (error) {
      setDeleteError(
        error instanceof Error
          ? error.message
          : 'Gagal menghapus percakapan terpilih.'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <section
      className={`fixed inset-y-0 right-0 z-[60] overflow-hidden border-l border-white/10 font-body text-white transition-[left] duration-300 md:z-40 ${
        sidebarVisible ? 'left-0 md:left-72' : 'left-0'
      }`}
      style={{
        background:
          'radial-gradient(circle at 50% 42%, rgba(43, 78, 170, 0.24) 0%, rgba(16, 27, 72, 0.14) 30%, rgba(0, 0, 0, 0) 64%), linear-gradient(180deg, #000000 0%, #010208 52%, #000000 100%)',
      }}
    >
      <div className="relative z-10 flex h-full min-h-0 flex-col">
        <div className="shrink-0 px-4 pt-5 sm:px-6 md:px-10 md:pt-8 lg:px-14">
          <div className="mx-auto w-full max-w-5xl">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onBack}
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05] text-white/65 transition-colors hover:bg-white/[0.10] hover:text-white"
                aria-label="Tutup pencarian percakapan"
              >
                <span className="material-symbols-outlined">
                  arrow_back
                </span>
              </button>

              <div className="relative min-w-0 flex-1">
                <span className="material-symbols-outlined pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[23px] text-white/45">
                  search
                </span>
                <input
                  type="text"
                  value={searchKeyword}
                  onChange={(event) =>
                    setSearchKeyword(event.target.value)
                  }
                  placeholder="Cari pertanyaan Anda"
                  autoFocus
                  className="h-12 w-full rounded-2xl border border-white/10 bg-[rgba(27,29,38,0.90)] py-3 pl-14 pr-12 text-[15px] text-white outline-none shadow-[0_14px_40px_rgba(0,0,0,0.34)] backdrop-blur-md placeholder:text-white/35 transition-all focus:border-primary/70 focus:ring-1 focus:ring-primary/30"
                />
                {searchKeyword && (
                  <button
                    type="button"
                    onClick={() => setSearchKeyword('')}
                    className="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-xl text-white/40 hover:bg-white/[0.08] hover:text-white"
                    aria-label="Bersihkan pencarian"
                  >
                    <span className="material-symbols-outlined text-[19px]">
                      close
                    </span>
                  </button>
                )}
              </div>
            </div>

            <div className="my-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
                  Riwayat percakapan
                </p>
                <h1 className="mt-1 font-headline text-xl font-semibold text-white md:text-2xl">
                  Pertanyaan percakapan Anda
                </h1>
                <p className="mt-1 text-xs text-white/40">
                  {questionCount} pertanyaan dalam{' '}
                  {filteredConversations.length} percakapan
                </p>
              </div>

              {!isSelectionMode ? (
                <button
                  type="button"
                  onClick={() => setIsSelectionMode(true)}
                  disabled={filteredConversations.length === 0}
                  className="flex items-center gap-2 rounded-2xl border border-primary/35 bg-primary/10 px-4 py-2.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <span className="material-symbols-outlined text-[18px]">
                    select_check_box
                  </span>
                  Pilih percakapan
                </button>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={toggleSelectAllFiltered}
                    className="rounded-2xl border border-white/10 bg-white/[0.05] px-3 py-2.5 text-xs font-semibold text-white/70 hover:bg-white/[0.10] hover:text-white"
                  >
                    {allFilteredSelected
                      ? 'Batalkan semua pilihan'
                      : 'Pilih semua'}
                  </button>
                  <button
                    type="button"
                    onClick={exitSelectionMode}
                    className="rounded-2xl px-3 py-2.5 text-xs font-semibold text-white/55 hover:bg-white/[0.06] hover:text-white"
                  >
                    Batal
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setDeleteError(null);
                      setIsDeleteConfirmOpen(true);
                    }}
                    disabled={selectedCount === 0}
                    className="flex items-center gap-2 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-3 py-2.5 text-xs font-semibold text-rose-300 hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <span className="material-symbols-outlined text-[18px]">
                      delete
                    </span>
                    Hapus {selectedCount || ''}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 px-4 pb-8 sm:px-6 md:px-10 lg:px-14">
          <div className="custom-scrollbar mx-auto h-full w-full max-w-5xl space-y-3 overflow-y-auto overscroll-contain pr-1">
            {filteredConversations.length > 0 ? (
              filteredConversations.map((conversation) => {
                const isSelected =
                  selectedConversationIds.has(conversation.id);
                const questions =
                  conversation.questions.length > 0
                    ? conversation.questions
                    : [
                        {
                          id: '',
                          content: conversation.title,
                          dateLabel: conversation.dateLabel,
                        },
                      ];

                return (
                  <article
                    key={conversation.id}
                    className={`overflow-hidden rounded-3xl border transition-colors ${
                      isSelected
                        ? 'border-primary/45 bg-primary/[0.09]'
                        : 'border-white/10 bg-[rgba(17,19,26,0.78)]'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        isSelectionMode
                          ? toggleConversationSelection(
                              conversation.id
                            )
                          : handleQuestionClick(conversation)
                      }
                      className="flex w-full items-center gap-3 border-b border-white/[0.07] px-4 py-3 text-left sm:px-5"
                    >
                      {isSelectionMode ? (
                        <span
                          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                            isSelected
                              ? 'border-primary bg-primary text-[#001018]'
                              : 'border-white/25 text-transparent'
                          }`}
                        >
                          <span className="material-symbols-outlined text-[16px]">
                            check
                          </span>
                        </span>
                      ) : (
                        <span className="material-symbols-outlined text-[19px] text-primary/80">
                          forum
                        </span>
                      )}

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-white/85">
                          {conversation.title}
                        </p>
                        <p className="mt-0.5 text-[11px] text-white/35">
                          {questions.length} pertanyaan
                        </p>
                      </div>

                      {conversation.pinned && (
                        <span className="material-symbols-outlined text-[16px] text-primary">
                          push_pin
                        </span>
                      )}
                      <span className="font-mono text-[10px] text-white/30">
                        {conversation.dateLabel}
                      </span>
                    </button>

                    <div className="divide-y divide-white/[0.06]">
                      {questions.map((question, index) => (
                        <button
                          key={question.id || `${conversation.id}-${index}`}
                          type="button"
                          onClick={() =>
                            handleQuestionClick(
                              conversation,
                              question.id || undefined
                            )
                          }
                          className="group flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-white/[0.045] sm:px-5"
                        >
                          <span className="material-symbols-outlined shrink-0 text-[18px] text-white/30 transition-colors group-hover:text-primary">
                            chat_bubble
                          </span>
                          <p className="min-w-0 flex-1 truncate text-sm text-white/72 transition-colors group-hover:text-white">
                            {question.content}
                          </p>
                          <span className="shrink-0 font-mono text-[10px] text-white/28">
                            {question.dateLabel}
                          </span>
                          {!isSelectionMode && (
                            <span className="material-symbols-outlined shrink-0 text-[18px] text-white/20 transition-all group-hover:translate-x-0.5 group-hover:text-primary">
                              arrow_forward
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </article>
                );
              })
            ) : (
              <div className="flex h-full min-h-[260px] flex-col items-center justify-center rounded-3xl border border-white/10 bg-white/[0.025] px-6 text-center">
                <span className="material-symbols-outlined mb-3 text-[42px] text-white/20">
                  search_off
                </span>
                <p className="font-headline text-base font-semibold text-white/80">
                  Percakapan tidak ditemukan
                </p>
                <p className="mt-1 text-sm text-white/35">
                  Coba pertanyaan atau kata kunci lain.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {isDeleteConfirmOpen && (
        <div
          className="fixed inset-0 z-[120] flex items-center justify-center bg-black/75 px-4 backdrop-blur-sm"
          role="presentation"
          onMouseDown={(event) => {
            if (
              event.target === event.currentTarget &&
              !isDeleting
            ) {
              setIsDeleteConfirmOpen(false);
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-conversations-title"
            className="w-full max-w-md rounded-3xl border border-white/10 bg-[#11131a] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.70)]"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-rose-400/25 bg-rose-500/10 text-rose-300">
              <span className="material-symbols-outlined text-[26px]">
                delete_forever
              </span>
            </div>
            <h2
              id="delete-conversations-title"
              className="mt-5 font-headline text-xl font-semibold text-white"
            >
              Hapus percakapan terpilih?
            </h2>
            <p className="mt-2 text-sm leading-6 text-white/55">
              Anda akan menghapus {selectedCount} percakapan.
              Tindakan ini tidak dapat dibatalkan.
            </p>

            {deleteError && (
              <div className="mt-4 rounded-2xl border border-rose-400/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                {deleteError}
              </div>
            )}

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => {
                  if (!isDeleting) {
                    setIsDeleteConfirmOpen(false);
                    setDeleteError(null);
                  }
                }}
                disabled={isDeleting}
                className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-semibold text-white/70 hover:bg-white/[0.08] hover:text-white disabled:opacity-50"
              >
                Tidak, Batal
              </button>
              <button
                type="button"
                onClick={() => void confirmDeleteSelected()}
                disabled={isDeleting}
                className="flex items-center justify-center gap-2 rounded-2xl border border-rose-400/30 bg-rose-500 px-4 py-3 text-sm font-semibold text-white hover:bg-rose-400 disabled:opacity-60"
              >
                <span className="material-symbols-outlined text-[19px]">
                  {isDeleting
                    ? 'progress_activity'
                    : 'delete'}
                </span>
                {isDeleting ? 'Menghapus...' : 'Ya, Hapus'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
