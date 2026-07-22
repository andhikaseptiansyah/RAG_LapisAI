import React, { useMemo, useState } from 'react';

import type { Message } from '../types';
import type { ChatLanguage } from '../services/chatService';

interface ConversationNavigatorPanelProps {
  isOpen: boolean;
  onClose: () => void;
  messages: Message[];
  detectedLanguage: ChatLanguage;
  onLanguageChange: (language: ChatLanguage) => void;
  onSelectMessage: (messageId: string) => void;
}

interface ConversationQuestion {
  id: string;
  content: string;
  time?: string;
  attachmentCount: number;
  position: number;
}

export const ConversationNavigatorPanel: React.FC<
  ConversationNavigatorPanelProps
> = ({
  isOpen,
  onClose,
  messages,
  detectedLanguage,
  onLanguageChange,
  onSelectMessage,
}) => {
  const [searchKeyword, setSearchKeyword] = useState('');

  const questions = useMemo<ConversationQuestion[]>(() => {
    let position = 0;

    return messages.flatMap((message) => {
      if (message.role !== 'user') {
        return [];
      }

      position += 1;

      return [
        {
          id: message.id,
          content: message.content.trim() || 'Pesan dengan lampiran',
          time: message.time,
          attachmentCount: message.attachments?.length ?? 0,
          position,
        },
      ];
    });
  }, [messages]);

  const filteredQuestions = useMemo(() => {
    const normalizedKeyword = searchKeyword.trim().toLocaleLowerCase();

    if (!normalizedKeyword) {
      return questions;
    }

    return questions.filter((question) =>
      question.content.toLocaleLowerCase().includes(normalizedKeyword)
    );
  }, [questions, searchKeyword]);

  const handleQuestionClick = (messageId: string) => {
    onSelectMessage(messageId);

    if (window.matchMedia('(max-width: 767px)').matches) {
      onClose();
    }
  };

  return (
    <>
      {/* Overlay Background */}
      <div
        className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-all duration-300 md:hidden ${
          isOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className={`absolute right-0 z-50 flex h-full shrink-0 transform flex-col overflow-hidden bg-[#050505] shadow-[-10px_0_40px_rgba(0,0,0,0.5)] transition-all duration-300 md:relative ${
          isOpen
            ? 'w-[300px] translate-x-0 border-l border-[#1a1a1a] opacity-100 md:w-[340px]'
            : 'translate-x-full border-transparent opacity-0 md:w-0 md:translate-x-0'
        }`}
        aria-label="Navigasi percakapan aktif"
      >
        <div className="flex h-full min-h-0 flex-col px-5 pb-5 pt-6">
          
          {/* Header Section */}
          <header className="relative flex items-center justify-between pb-6">
            
            {/* Tombol Tutup */}
            <button
              type="button"
              onClick={onClose}
              className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#111] text-white/50 transition-all hover:bg-[#1a1a1a] hover:text-white"
              aria-label="Tutup navigasi percakapan aktif"
              title="Tutup navigasi percakapan aktif"
            >
              <span className="material-symbols-outlined text-[20px]">
                right_panel_close
              </span>
            </button>

            {/* Logo Image */}
            <div className="absolute left-1/2 top-0 flex h-8 -translate-x-1/2 items-center justify-center pointer-events-none">
              <img
                src="/assistant-logo.png"
                alt="Logo Lapis AI"
                className="h-[100px] w-auto shrink-0 select-none object-contain"
                draggable="false"
              />
            </div>

            {/* Question Count Badge */}
            <div className="relative z-10 flex h-7 shrink-0 items-center justify-center rounded-md bg-[#111] px-2 font-mono text-[11px] text-white/40 border border-[#1a1a1a]">
              {String(questions.length).padStart(2, '0')}
            </div>
          </header>

          {/* Language Selection (Transparent Cards) */}
          <section className="py-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">
                  Bahasa jawaban
                </p>
                <p className="mt-1 text-[11px] text-white/40">
                  Pilih bahasa yang digunakan untuk jawaban.
                </p>
              </div>

              <span className="material-symbols-outlined rounded-full bg-[#111] p-1.5 text-[18px] text-white/40">
                translate
              </span>
            </div>

            <div className="flex gap-2 w-full">
              {(['ID', 'EN'] as ChatLanguage[]).map((language) => {
                const isSelected = language === detectedLanguage;

                return (
                  <button
                    key={language}
                    type="button"
                    onClick={() => onLanguageChange(language)}
                    className={`flex-1 rounded-xl px-4 py-3 text-left transition-all duration-200 border ${
                      isSelected
                        ? 'border-[#333] bg-transparent text-white'
                        : 'border-transparent bg-transparent text-white/40 hover:border-[#1a1a1a] hover:text-white/80'
                    }`}
                  >
                    <span className="block font-mono text-[12px] font-bold">
                      {language}
                    </span>
                    <span className={`mt-0.5 block truncate text-[10px] ${isSelected ? 'text-white/60' : 'text-white/30'}`}>
                      {language === 'ID' ? 'Bahasa Indonesia' : 'Bahasa Inggris'}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Search & Questions List */}
          <section className="flex min-h-0 flex-1 flex-col pt-5">
            <div className="mb-4 flex items-end justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">
                  Pertanyaan dalam percakapan ini
                </p>
                <p className="mt-1 text-[11px] text-white/40">
                  Pilih pertanyaan untuk membuka posisinya.
                </p>
              </div>

              {searchKeyword && (
                <span className="rounded-md bg-[#111] px-2 py-0.5 font-mono text-[10px] text-white/50 border border-[#1a1a1a]">
                  {filteredQuestions.length}/{questions.length}
                </span>
              )}
            </div>

            <div className="relative mb-4 group">
              <span className="material-symbols-outlined pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[18px] text-white/30 transition-colors group-focus-within:text-white/60">
                search
              </span>
              <input
                value={searchKeyword}
                onChange={(event) => setSearchKeyword(event.target.value)}
                placeholder="Cari dalam percakapan ini"
                className="h-12 w-full rounded-xl border border-[#1a1a1a] bg-[#0c0c0c] pl-11 pr-10 text-[13px] text-white/90 outline-none transition-all duration-200 placeholder:text-white/30 focus:border-[#333] focus:bg-[#111] focus:ring-2 focus:ring-[#333]/30"
              />
              {searchKeyword && (
                <button
                  type="button"
                  onClick={() => setSearchKeyword('')}
                  className="absolute right-2.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md bg-[#1a1a1a] text-white/50 transition-colors hover:bg-[#2a2a2a] hover:text-white"
                  aria-label="Bersihkan pencarian"
                >
                  <span className="material-symbols-outlined text-[16px]">
                    close
                  </span>
                </button>
              )}
            </div>

            <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-2">
              {questions.length === 0 ? (
                <div className="flex h-full min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-[#1a1a1a] bg-[#080808]/50 px-6 text-center">
                  <div className="rounded-full bg-[#111] p-4 mb-3 border border-[#1a1a1a]">
                    <span className="material-symbols-outlined text-[28px] text-white/20">
                      format_list_bulleted
                    </span>
                  </div>
                  <p className="text-[14px] font-medium text-white/70">
                    Belum ada pertanyaan
                  </p>
                  <p className="mt-1.5 max-w-[220px] text-[11px] leading-relaxed text-white/40">
                    Pertanyaan dari percakapan ini akan muncul setelah Anda mengirimkannya.
                  </p>
                </div>
              ) : filteredQuestions.length === 0 ? (
                <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-[#1a1a1a] bg-[#080808]/50 px-6 text-center">
                  <span className="material-symbols-outlined text-[30px] text-white/20">
                    search_off
                  </span>
                  <p className="mt-3 text-[12px] text-white/50">
                    Pertanyaan yang sesuai tidak ditemukan.
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-1.5 pb-2">
                  {filteredQuestions.map((question) => (
                    <button
                      key={question.id}
                      type="button"
                      onClick={() => handleQuestionClick(question.id)}
                      className="group relative flex w-full items-start gap-3 rounded-xl border border-transparent p-3 text-left transition-all duration-200 hover:border-[#1a1a1a] hover:bg-[#0c0c0c]"
                      title={question.content}
                    >
                      <span className="mt-0.5 flex w-6 shrink-0 items-center justify-center rounded bg-[#111] py-0.5 font-mono text-[9px] font-medium text-white/40 transition-colors group-hover:bg-[#1a1a1a] group-hover:text-white/80">
                        {String(question.position).padStart(2, '0')}
                      </span>

                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 block text-[13px] leading-relaxed text-white/70 transition-colors group-hover:text-white/95">
                          {question.content}
                        </span>

                        {(question.time || question.attachmentCount > 0) && (
                          <span className="mt-2 flex items-center gap-3 font-mono text-[10px] text-white/30">
                            {question.time && (
                              <span className="flex items-center gap-1">
                                <span className="material-symbols-outlined text-[12px]">schedule</span>
                                {question.time}
                              </span>
                            )}
                            {question.attachmentCount > 0 && (
                              <span className="flex items-center gap-1 rounded bg-[#111] px-1.5 py-0.5">
                                <span className="material-symbols-outlined text-[12px]">
                                  attach_file
                                </span>
                                {question.attachmentCount}
                              </span>
                            )}
                          </span>
                        )}
                      </span>

                      <span className="material-symbols-outlined mt-0.5 shrink-0 text-[18px] text-white/10 transition-all duration-200 group-hover:translate-x-1 group-hover:text-white/40">
                        arrow_forward
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>
      </aside>
    </>
  );
};

export default ConversationNavigatorPanel;