import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';

import { ConversationSearch } from './ConversationSearch';
import { useAuth } from '../hooks/useAuth';
import { conversationService } from '../services/conversationService';
import type { ConversationHistory } from './ConversationSearch';
import type { ConversationSummary } from '../services/conversationService';

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
  lastMessage?: string;
  lastUserMessage?: string;
}

interface MenuPosition {
  top: number;
  left: number;
}

const toDateLabel = (value?: string): string => {
  if (!value) {
    return 'Latest';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return 'Latest';
  }

  const now = new Date();
  const today = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  );
  const targetDate = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate()
  );

  const diffMs = today.getTime() - targetDate.getTime();
  const diffDays = Math.round(
    diffMs / (1000 * 60 * 60 * 24)
  );

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';

  return date.toLocaleDateString('en-US', {
    day: '2-digit',
    month: 'short',
  });
};


const normalizeConversationTitle = (
  value?: string
): string => {
  const title = value?.trim() ?? '';

  if (!title) {
    return '';
  }

  if (title.toLowerCase() === 'new conversation') {
    return '';
  }

  return title;
};

const buildConversationDisplayTitle = (
  conversation: ConversationSummary
): string => {
  const customTitle = normalizeConversationTitle(
    conversation.title
  );

  if (customTitle) {
    return customTitle;
  }

  const lastUserMessage =
    conversation.last_user_message?.trim();

  if (lastUserMessage) {
    return lastUserMessage;
  }

  const lastMessage =
    conversation.last_message?.trim();

  if (lastMessage) {
    return lastMessage;
  }

  return 'New Conversation';
};

const mapConversationToRecentChat = (
  conversation: ConversationSummary
): RecentChat => {
  const dateValue =
    conversation.last_message_at ??
    conversation.updated_at ??
    conversation.created_at;

  return {
    id: conversation.id,
    title: buildConversationDisplayTitle(
      conversation
    ),
    pinned: Boolean(
      conversation.is_pinned ?? conversation.pinned
    ),
    dateLabel: toDateLabel(dateValue),
    group: 'Latest',
    lastMessage: conversation.last_message,
    lastUserMessage: conversation.last_user_message,
  };
};

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  onNewChat,
  onSelectConversation,
}) => {
  const navigate = useNavigate();
  const { user, isAdmin, logout } = useAuth();

  const [recentChats, setRecentChats] =
    useState<RecentChat[]>([]);

  const [isLoadingChats, setIsLoadingChats] =
    useState(false);

  const [historyError, setHistoryError] =
    useState<string | null>(null);

  const [openMenuId, setOpenMenuId] =
    useState<string | null>(null);

  const [menuPosition, setMenuPosition] =
    useState<MenuPosition | null>(null);

  const [
    isConversationSearchOpen,
    setIsConversationSearchOpen,
  ] = useState(false);

  const loadRecentChats = useCallback(async () => {
    setIsLoadingChats(true);
    setHistoryError(null);

    try {
      const conversations =
        await conversationService.list();

      setRecentChats(
        conversations.map(
          mapConversationToRecentChat
        )
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to load conversation history.';

      setHistoryError(message);
      setRecentChats([]);
    } finally {
      setIsLoadingChats(false);
    }
  }, []);

  useEffect(() => {
    void loadRecentChats();
  }, [loadRecentChats]);

  useEffect(() => {
    if (isOpen) {
      void loadRecentChats();
    }
  }, [isOpen, loadRecentChats]);

  useEffect(() => {
    const handleConversationsChanged = () => {
      void loadRecentChats();
    };

    window.addEventListener(
      'lapisai:conversations-changed',
      handleConversationsChanged
    );

    return () => {
      window.removeEventListener(
        'lapisai:conversations-changed',
        handleConversationsChanged
      );
    };
  }, [loadRecentChats]);

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


  useEffect(() => {
    if (!openMenuId) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;

      if (
        target?.closest('[data-conversation-menu]') ||
        target?.closest(
          '[data-conversation-menu-trigger]'
        )
      ) {
        return;
      }

      setOpenMenuId(null);
      setMenuPosition(null);
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenMenuId(null);
        setMenuPosition(null);
      }
    };

    const closeMenu = () => {
      setOpenMenuId(null);
      setMenuPosition(null);
    };

    document.addEventListener(
      'mousedown',
      handlePointerDown
    );
    document.addEventListener('keydown', handleEscape);
    window.addEventListener('resize', closeMenu);
    window.addEventListener('scroll', closeMenu, true);

    return () => {
      document.removeEventListener(
        'mousedown',
        handlePointerDown
      );
      document.removeEventListener(
        'keydown',
        handleEscape
      );
      window.removeEventListener('resize', closeMenu);
      window.removeEventListener(
        'scroll',
        closeMenu,
        true
      );
    };
  }, [openMenuId]);

  const handleConversationMenuClick = (
    event: React.MouseEvent<HTMLButtonElement>,
    chatId: string
  ) => {
    event.stopPropagation();

    if (openMenuId === chatId) {
      setOpenMenuId(null);
      setMenuPosition(null);
      return;
    }

    const rect =
      event.currentTarget.getBoundingClientRect();

    const menuWidth = 224;
    const menuHeight = 218;
    const gap = 8;
    const viewportPadding = 12;

    const preferredLeft = rect.right + gap;
    const fallbackLeft = rect.left - menuWidth - gap;
    const hasRightSpace =
      preferredLeft + menuWidth + viewportPadding <=
      window.innerWidth;

    const left = hasRightSpace
      ? preferredLeft
      : Math.max(viewportPadding, fallbackLeft);

    const centerTop = rect.top + rect.height / 2;
    const minTop = viewportPadding + menuHeight / 2;
    const maxTop =
      window.innerHeight -
      viewportPadding -
      menuHeight / 2;

    const top = Math.min(
      Math.max(centerTop, minTop),
      maxTop
    );

    setMenuPosition({ top, left });
    setOpenMenuId(chatId);
  };

  const handleShareChat = async (
    chat: RecentChat
  ) => {
    setOpenMenuId(null);
    setMenuPosition(null);

    try {
      await navigator.clipboard.writeText(
        `${window.location.origin}/?conversationId=${chat.id}`
      );

      window.alert(
        'Conversation link copied successfully.'
      );
    } catch {
      window.alert(
        `Share conversation: ${chat.title}`
      );
    }
  };

  const handleTogglePin = async (
    chat: RecentChat
  ) => {
    setOpenMenuId(null);
    setMenuPosition(null);

    const nextPinnedState = !chat.pinned;

    try {
      const updatedConversation =
        await conversationService.setPinned(
          chat.id,
          nextPinnedState
        );

      setRecentChats((previousChats) =>
        previousChats.map((item) =>
          item.id === chat.id
            ? mapConversationToRecentChat(
                updatedConversation
              )
            : item
        )
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to update pin status.';

      window.alert(message);
    }
  };

  const handleRenameChat = async (
    chat: RecentChat
  ) => {
    const newTitle = window.prompt(
      'Rename conversation',
      chat.title
    );

    setOpenMenuId(null);
    setMenuPosition(null);

    if (!newTitle || !newTitle.trim()) {
      return;
    }

    try {
      const updatedConversation =
        await conversationService.rename(
          chat.id,
          newTitle.trim()
        );

      setRecentChats((previousChats) =>
        previousChats.map((item) =>
          item.id === chat.id
            ? mapConversationToRecentChat(
                updatedConversation
              )
            : item
        )
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to save conversation name.';

      window.alert(message);
    }
  };

  const handleDeleteChat = async (
    chat: RecentChat
  ) => {
    const shouldDelete = window.confirm(
      `Delete conversation "${chat.title}"?`
    );

    if (!shouldDelete) {
      return;
    }

    setOpenMenuId(null);
    setMenuPosition(null);

    try {
      await conversationService.remove(chat.id);

      setRecentChats((previousChats) =>
        previousChats.filter(
          (item) => item.id !== chat.id
        )
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to delete conversation.';

      window.alert(message);
    }
  };

  const handleNewChat = () => {
    setOpenMenuId(null);
    setMenuPosition(null);
    setIsConversationSearchOpen(false);
    onNewChat();
  };

  const handleLogout = (): void => {
    setOpenMenuId(null);
    setMenuPosition(null);
    logout();
    navigate('/login', { replace: true });
  };

  const handleOpenConversationSearch = () => {
    setOpenMenuId(null);
    setMenuPosition(null);
    setIsConversationSearchOpen(true);
  };

  const handleCloseConversationSearch = () => {
    setIsConversationSearchOpen(false);
  };

  const handleSelectConversation = (
    conversation: ConversationHistory
  ) => {
    setIsConversationSearchOpen(false);
    setOpenMenuId(null);
    setMenuPosition(null);

    onSelectConversation?.(conversation.id);
  };

  return (
    <>
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
            aria-label="Close sidebar"
            title="Close sidebar"
          >
            <span className="material-symbols-outlined">
              close
            </span>
          </button>
        </div>

        <nav className="flex min-w-[200px] flex-col gap-1">
          <button
            type="button"
            onClick={handleNewChat}
            className="flex w-full items-center gap-3 whitespace-nowrap px-1 py-2.5 text-left font-mono text-sm text-white transition-colors hover:text-primary"
          >
            <span className="material-symbols-outlined text-[21px]">
              edit_square
            </span>

            New Chat
          </button>

          <button
            type="button"
            onClick={handleOpenConversationSearch}
            className="flex w-full items-center gap-3 whitespace-nowrap px-1 py-2.5 text-left font-mono text-sm text-white transition-colors hover:text-primary"
          >
            <span className="material-symbols-outlined text-[21px]">
              search
            </span>

            Search Chats
          </button>

          {isAdmin && (
            <Link
              to="/admin"
              onClick={onClose}
              className="flex w-full items-center gap-3 whitespace-nowrap px-1 py-2.5 text-left font-mono text-sm text-white transition-colors hover:text-primary"
            >
              <span className="material-symbols-outlined text-[21px]">
                admin_panel_settings
              </span>

              Admin Panel
            </Link>
          )}
        </nav>

        <div className="mt-8 min-h-0 min-w-[200px] flex-1 overflow-hidden">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="font-mono text-[10px] uppercase tracking-wider text-white/45">
              Recent Chats
            </p>

            {sortedChats.length > 0 && (
              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-white/35">
                {sortedChats.length}
              </span>
            )}
          </div>

          <div className="relative h-full min-h-0">
            <div className="pointer-events-none absolute left-0 right-2 top-0 z-10 h-4 bg-gradient-to-b from-black to-transparent" />
            <div className="pointer-events-none absolute bottom-0 left-0 right-2 z-10 h-6 bg-gradient-to-t from-black to-transparent" />

            <div className="custom-scrollbar h-full overflow-y-auto pb-6 pr-2">
              <div className="flex flex-col gap-1">
                {isLoadingChats ? (
                  <p className="py-2 text-xs text-white/40">
                    Loading history...
                  </p>
                ) : historyError ? (
                  <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                    {historyError}
                  </div>
                ) : sortedChats.length > 0 ? (
                  sortedChats.map((chat) => (
                    <div
                      key={chat.id}
                      className="group relative flex min-w-0 items-center gap-2 rounded-xl px-1 transition-colors hover:bg-white/[0.03]"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          handleSelectConversation({
                            id: chat.id,
                            title: chat.title,
                            dateLabel: chat.dateLabel,
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
                            title="Pinned conversation"
                          >
                            push_pin
                          </span>
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={(event) =>
                          handleConversationMenuClick(
                            event,
                            chat.id
                          )
                        }
                        data-conversation-menu-trigger="true"
                        className={`
                          flex h-8 w-8
                          shrink-0
                          items-center
                          justify-center
                          rounded-lg
                          transition-all
                          ${
                            openMenuId === chat.id
                              ? 'bg-white/10 text-white'
                              : 'text-white/50 hover:bg-white/5 hover:text-white'
                          }
                        `}
                        aria-label={`Conversation menu ${chat.title}`}
                        title="Conversation menu"
                      >
                        <span className="material-symbols-outlined text-[20px]">
                          more_horiz
                        </span>
                      </button>

                      {openMenuId === chat.id &&
                        menuPosition &&
                        createPortal(
                          <div
                            data-conversation-menu="true"
                            className="animate-fadeIn fixed z-[1000] w-56 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#1b1b1b] p-2 shadow-[0_14px_36px_rgba(0,0,0,0.65)]"
                            style={{
                              top: menuPosition.top,
                              left: menuPosition.left,
                            }}
                          >
                            <button
                              type="button"
                              onClick={() =>
                                handleShareChat(chat)
                              }
                              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white"
                            >
                              <span className="material-symbols-outlined text-[19px]">
                                share
                              </span>

                              Share conversation
                            </button>

                            <button
                              type="button"
                              onClick={() =>
                                handleTogglePin(chat)
                              }
                              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white"
                            >
                              <span className="material-symbols-outlined text-[19px]">
                                push_pin
                              </span>

                              {chat.pinned
                                ? 'Unpin'
                                : 'Pin'}
                            </button>

                            <button
                              type="button"
                              onClick={() =>
                                handleRenameChat(chat)
                              }
                              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white"
                            >
                              <span className="material-symbols-outlined text-[19px]">
                                edit
                              </span>

                              Rename
                            </button>

                            <div className="my-1 border-t border-white/10" />

                            <button
                              type="button"
                              onClick={() =>
                                handleDeleteChat(chat)
                              }
                              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-red-400 transition-colors hover:bg-red-500/10"
                            >
                              <span className="material-symbols-outlined text-[19px]">
                                delete
                              </span>

                              Delete
                            </button>
                          </div>,
                          document.body
                        )}
                    </div>
                  ))
                ) : (
                  <p className="py-2 text-xs text-white/40">
                    No conversations yet.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="min-w-[200px] border-t border-white/10 pt-4">
          <div className="mb-3 flex items-center gap-3 rounded-2xl bg-white/5 px-3 py-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 text-primary">
              <span className="material-symbols-outlined text-[19px]">
                person
              </span>
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm text-white">
                {user?.name ?? user?.username ?? 'Staff'}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-white/45">
                {user?.role ?? 'staff'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left font-mono text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
          >
            <span className="material-symbols-outlined text-[20px]">
              logout
            </span>
            Logout
          </button>
        </div>
      </aside>

      {isConversationSearchOpen && (
        <ConversationSearch
          conversations={conversationHistory}
          onSelectConversation={handleSelectConversation}
          onBack={handleCloseConversationSearch}
          sidebarVisible={isOpen}
        />
      )}
    </>
  );
};
