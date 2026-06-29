import React, { useMemo, useState } from 'react';
import { ConversationSearch } from './ConversationSearch';
import type { ConversationHistory } from './ConversationSearch';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConversation?: (
    conversationId: string
  ) => void;
}

interface RecentChat {
  id: string;
  title: string;
  pinned: boolean;
  dateLabel: string;
  group: string;
}

const initialRecentChats: RecentChat[] = [
  {
    id: 'chat-001',
    title: 'Kebijakan Work From Home',
    pinned: true,
    dateLabel: 'Hari ini',
    group: 'Terbaru',
  },
  {
    id: 'chat-002',
    title: 'Format Laporan Keuangan',
    pinned: false,
    dateLabel: 'Hari ini',
    group: 'Terbaru',
  },
  {
    id: 'chat-003',
    title: 'Kebijakan Klaim Medis',
    pinned: false,
    dateLabel: 'Hari ini',
    group: 'Terbaru',
  },
  {
    id: 'chat-004',
    title: 'Template Laporan Bulanan',
    pinned: false,
    dateLabel: 'Kemarin',
    group: 'Terbaru',
  },
  {
    id: 'chat-005',
    title: 'Ringkasan Dokumen HR',
    pinned: false,
    dateLabel: 'Kemarin',
    group: 'Terbaru',
  },
  {
    id: 'chat-006',
    title: 'Prosedur Klaim Rawat Inap',
    pinned: false,
    dateLabel: '27 Jun',
    group: 'Terbaru',
  },
  {
    id: 'chat-007',
    title: 'SOP Onboarding Karyawan',
    pinned: false,
    dateLabel: '27 Jun',
    group: 'Terbaru',
  },
  {
    id: 'chat-008',
    title: 'Kebijakan Cuti Tahunan',
    pinned: false,
    dateLabel: '26 Jun',
    group: 'Terbaru',
  },
  {
    id: 'chat-009',
    title: 'Panduan Akses Sistem Internal',
    pinned: false,
    dateLabel: '25 Jun',
    group: 'Terbaru',
  },
];

export const Sidebar: React.FC<
  SidebarProps
> = ({
  isOpen,
  onClose,
  onNewChat,
  onSelectConversation,
}) => {
  const [recentChats, setRecentChats] =
    useState<RecentChat[]>(
      initialRecentChats
    );

  const [openMenuId, setOpenMenuId] =
    useState<string | null>(null);

  const [
    isConversationSearchOpen,
    setIsConversationSearchOpen,
  ] = useState(false);

  const sortedChats = useMemo(() => {
    return [...recentChats].sort(
      (chatA, chatB) =>
        Number(chatB.pinned) -
        Number(chatA.pinned)
    );
  }, [recentChats]);

  const conversationHistory =
    useMemo<ConversationHistory[]>(() => {
      return sortedChats.map((chat) => ({
        id: chat.id,
        title: chat.title,
        dateLabel: chat.dateLabel,
        group: chat.group,
        pinned: chat.pinned,
      }));
    }, [sortedChats]);

  const handleShareChat = async (
    chat: RecentChat
  ) => {
    setOpenMenuId(null);

    try {
      await navigator.clipboard.writeText(
        `Lapis Knowledge Chat: ${chat.title}`
      );

      window.alert(
        'Link percakapan berhasil disalin.'
      );
    } catch {
      window.alert(
        `Bagikan percakapan: ${chat.title}`
      );
    }
  };

  const handleTogglePin = (
    chatId: string
  ) => {
    setRecentChats((previousChats) =>
      previousChats.map((chat) =>
        chat.id === chatId
          ? {
              ...chat,
              pinned: !chat.pinned,
            }
          : chat
      )
    );

    setOpenMenuId(null);
  };

  const handleRenameChat = (
    chat: RecentChat
  ) => {
    const newTitle = window.prompt(
      'Ganti nama percakapan',
      chat.title
    );

    if (!newTitle || !newTitle.trim()) {
      setOpenMenuId(null);
      return;
    }

    setRecentChats((previousChats) =>
      previousChats.map((item) =>
        item.id === chat.id
          ? {
              ...item,
              title: newTitle.trim(),
            }
          : item
      )
    );

    setOpenMenuId(null);
  };

  const handleDeleteChat = (
    chat: RecentChat
  ) => {
    const shouldDelete = window.confirm(
      `Hapus percakapan "${chat.title}"?`
    );

    if (!shouldDelete) {
      return;
    }

    setRecentChats((previousChats) =>
      previousChats.filter(
        (item) => item.id !== chat.id
      )
    );

    setOpenMenuId(null);
  };

  const handleNewChat = () => {
    setOpenMenuId(null);
    setIsConversationSearchOpen(false);
    onNewChat();
  };

  const handleOpenConversationSearch =
    () => {
      setOpenMenuId(null);
      setIsConversationSearchOpen(true);
    };

  const handleCloseConversationSearch =
    () => {
      setIsConversationSearchOpen(false);
    };

  const handleSelectConversation = (
    conversation: ConversationHistory
  ) => {
    setIsConversationSearchOpen(false);

    onSelectConversation?.(
      conversation.id
    );
  };

  return (
    <>
      {/* Overlay mobile hanya tampil ketika search tertutup */}
      {!isConversationSearchOpen && (
        <div
          className={`
            fixed inset-0 z-40
            bg-black/70
            backdrop-blur-sm
            transition-opacity
            duration-300
            md:hidden
            ${
              isOpen
                ? 'opacity-100'
                : 'hidden opacity-0'
            }
          `}
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          absolute z-50
          h-full
          shrink-0
          transform
          flex-col
          overflow-hidden
          bg-black
          transition-all
          duration-300
          md:relative

          ${
            isConversationSearchOpen
              ? 'hidden md:flex'
              : 'flex'
          }

          ${
            isOpen
              ? `
                w-[280px]
                translate-x-0
                border-r border-white/10
                p-5
                opacity-100
                md:w-64
                md:p-6
              `
              : `
                -translate-x-full
                border-none
                p-0
                opacity-0
                md:w-0
                md:translate-x-0
              `
          }
        `}
      >
        {/* Logo */}
        <div className="relative mb-7 flex min-w-[200px] items-center justify-center">
          <img
            src="/assistant-logo.png"
            alt="Lapis Logo"
            className="h-auto w-28 shrink-0 object-contain md:w-36"
          />

          <button
            type="button"
            onClick={onClose}
            className="absolute right-0 p-1 text-white/60 transition-colors hover:text-white md:hidden"
            aria-label="Tutup sidebar"
            title="Tutup sidebar"
          >
            <span className="material-symbols-outlined">
              close
            </span>
          </button>
        </div>

        {/* Menu utama */}
        <nav className="flex min-w-[200px] flex-col gap-1">
          <button
            type="button"
            onClick={handleNewChat}
            className="flex w-full items-center gap-3 whitespace-nowrap px-1 py-2.5 text-left font-mono text-sm text-white transition-colors hover:text-primary"
          >
            <span className="material-symbols-outlined text-[21px]">
              edit_square
            </span>

            Obrolan Baru
          </button>

          <button
            type="button"
            onClick={
              handleOpenConversationSearch
            }
            className="flex w-full items-center gap-3 whitespace-nowrap px-1 py-2.5 text-left font-mono text-sm text-white transition-colors hover:text-primary"
          >
            <span className="material-symbols-outlined text-[21px]">
              search
            </span>

            Cari Obrolan
          </button>
        </nav>

        {/* Recent Chats */}
        <div className="custom-scrollbar mt-8 min-w-[200px] flex-1 overflow-y-auto">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-wider text-white/45">
            Recent Chats
          </p>

          <div className="flex flex-col gap-1">
            {sortedChats.length > 0 ? (
              sortedChats
                .slice(0, 5)
                .map((chat) => (
                  <div
                    key={chat.id}
                    className="group relative flex min-w-0 items-center gap-2"
                  >
                    {/* Buka percakapan */}
                    <button
                      type="button"
                      onClick={() =>
                        handleSelectConversation({
                          id: chat.id,
                          title: chat.title,
                          dateLabel:
                            chat.dateLabel,
                          group: chat.group,
                          pinned: chat.pinned,
                        })
                      }
                      className="flex min-w-0 flex-1 items-center gap-3 truncate py-2 text-left text-sm text-white/80 transition-colors hover:text-white"
                      title={chat.title}
                    >
                      <span className="material-symbols-outlined shrink-0 text-[17px] text-white/70">
                        chat_bubble
                      </span>

                      <span className="truncate">
                        {chat.title}
                      </span>

                      {chat.pinned && (
                        <span
                          className="material-symbols-outlined shrink-0 text-[15px] text-primary"
                          title="Percakapan disematkan"
                        >
                          push_pin
                        </span>
                      )}
                    </button>

                    {/* Tombol menu */}
                    <button
                      type="button"
                      onClick={() =>
                        setOpenMenuId(
                          (currentId) =>
                            currentId ===
                            chat.id
                              ? null
                              : chat.id
                        )
                      }
                      className={`
                        flex h-8 w-8
                        shrink-0
                        items-center
                        justify-center
                        rounded-lg
                        transition-all
                        ${
                          openMenuId ===
                          chat.id
                            ? 'bg-white/10 text-white'
                            : 'text-white/50 hover:bg-white/5 hover:text-white'
                        }
                      `}
                      aria-label={`Menu percakapan ${chat.title}`}
                      title="Menu percakapan"
                    >
                      <span className="material-symbols-outlined text-[20px]">
                        more_horiz
                      </span>
                    </button>

                    {/* Dropdown menu */}
                    {openMenuId ===
                      chat.id && (
                      <div className="animate-fadeIn absolute right-0 top-10 z-[70] w-56 rounded-2xl border border-white/10 bg-[#1b1b1b] p-2 shadow-[0_14px_36px_rgba(0,0,0,0.65)]">
                        <button
                          type="button"
                          onClick={() =>
                            handleShareChat(
                              chat
                            )
                          }
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white"
                        >
                          <span className="material-symbols-outlined text-[19px]">
                            share
                          </span>

                          Bagikan percakapan
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            handleTogglePin(
                              chat.id
                            )
                          }
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white"
                        >
                          <span className="material-symbols-outlined text-[19px]">
                            push_pin
                          </span>

                          {chat.pinned
                            ? 'Lepas sematan'
                            : 'Sematkan'}
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            handleRenameChat(
                              chat
                            )
                          }
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white"
                        >
                          <span className="material-symbols-outlined text-[19px]">
                            edit
                          </span>

                          Ganti nama
                        </button>

                        <div className="my-1 border-t border-white/10" />

                        <button
                          type="button"
                          onClick={() =>
                            handleDeleteChat(
                              chat
                            )
                          }
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-red-400 transition-colors hover:bg-red-500/10"
                        >
                          <span className="material-symbols-outlined text-[19px]">
                            delete
                          </span>

                          Hapus
                        </button>
                      </div>
                    )}
                  </div>
                ))
            ) : (
              <p className="py-2 text-xs text-white/40">
                Belum ada percakapan.
              </p>
            )}
          </div>
        </div>
      </aside>

      {/* Halaman pencarian */}
      {isConversationSearchOpen && (
        <ConversationSearch
          conversations={
            conversationHistory
          }
          onSelectConversation={
            handleSelectConversation
          }
          onBack={
            handleCloseConversationSearch
          }
          sidebarVisible={isOpen}
        />
      )}
    </>
  );
};