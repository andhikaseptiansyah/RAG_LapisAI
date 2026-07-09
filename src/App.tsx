import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

import type {
  AttachedFile,
} from './types';

import { useChat } from './hooks/useChat';
import { sanitizeMarkdown } from './utils/sanitizeMarkdown';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { WelcomeScreen } from './components/WelcomeScreen';
import { ChatFooter } from './components/ChatFooter';

type DetectedLanguage = 'ID' | 'EN';
type UploadMode = 'photo' | 'file';

const TypewriterMarkdown: React.FC<{
  content: string;
  animate?: boolean;
  onTick?: () => void;
  onDone?: () => void;
}> = ({
  content,
  animate = false,
  onTick,
  onDone,
}) => {
  const [visibleText, setVisibleText] =
    useState(animate ? '' : content);

  const [isDone, setIsDone] =
    useState(!animate);

  const onTickRef = useRef(onTick);
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onTickRef.current = onTick;
  }, [onTick]);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (!animate) {
      setVisibleText(content);
      setIsDone(true);
      return;
    }

    let index = 0;
    let isCancelled = false;

    setVisibleText('');
    setIsDone(false);

    const typingInterval =
      window.setInterval(() => {
        if (isCancelled) {
          return;
        }

        index += 1;
        setVisibleText(
          content.slice(0, index)
        );
        onTickRef.current?.();

        if (index >= content.length) {
          window.clearInterval(
            typingInterval
          );
          setIsDone(true);
          onDoneRef.current?.();
        }
      }, 6);

    return () => {
      isCancelled = true;
      window.clearInterval(
        typingInterval
      );
    };
  }, [content, animate]);

  return (
    <>
      <div
        className="prose prose-sm prose-invert prose-custom max-w-none text-on-surface leading-relaxed text-[13px] md:text-sm"
        dangerouslySetInnerHTML={{
          __html:
            sanitizeMarkdown(visibleText),
        }}
      />

      {!isDone && (
        <span className="inline-block w-1.5 h-4 ml-1 bg-primary/80 animate-pulse align-middle" />
      )}
    </>
  );
};

export const App: React.FC = () => {
  const [isFirstMessage, setIsFirstMessage] =
    useState(true);

  const [sidebarOpen, setSidebarOpen] =
    useState(false);

  const [inputValue, setInputValue] =
    useState('');

  const [attachedFiles, setAttachedFiles] =
    useState<AttachedFile[]>([]);

  const [isRecording, setIsRecording] =
    useState(false);

  const [
    showScrollBottom,
    setShowScrollBottom,
  ] = useState(false);

  const {
    messages,
    setMessages,
    isGenerating,
    sendMessage,
    loadConversation,
    setLanguage,
    stopGenerating,
    clearChat,
  } = useChat({
    initialLanguage: 'ID',
  });

  const [
    detectedLanguage,
    setDetectedLanguage,
  ] = useState<DetectedLanguage>('ID');

  const chatContainerRef =
    useRef<HTMLDivElement>(null);

  const fileInputRef =
    useRef<HTMLInputElement>(null);

  const scrollButtonHideTimeoutRef =
    useRef<ReturnType<
      typeof setTimeout
    > | null>(null);

  const recognitionRef =
    useRef<any>(null);

  useEffect(() => {
    const setAppHeight = () => {
      document.documentElement.style.setProperty(
        '--app-height',
        `${window.innerHeight}px`
      );
    };

    setAppHeight();

    window.addEventListener(
      'resize',
      setAppHeight
    );

    window.addEventListener(
      'orientationchange',
      setAppHeight
    );

    return () => {
      window.removeEventListener(
        'resize',
        setAppHeight
      );

      window.removeEventListener(
        'orientationchange',
        setAppHeight
      );
    };
  }, []);

  const scrollToBottom = useCallback(() => {
    if (scrollButtonHideTimeoutRef.current) {
      clearTimeout(
        scrollButtonHideTimeoutRef.current
      );
    }

    setShowScrollBottom(false);

    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top:
          chatContainerRef.current
            .scrollHeight,
        behavior: 'smooth',
      });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const handleScroll = () => {
    if (!chatContainerRef.current) {
      return;
    }

    const {
      scrollTop,
      scrollHeight,
      clientHeight,
    } = chatContainerRef.current;

    const shouldShowButton =
      scrollHeight -
        scrollTop -
        clientHeight >
      100;

    setShowScrollBottom(
      shouldShowButton
    );

    if (scrollButtonHideTimeoutRef.current) {
      clearTimeout(
        scrollButtonHideTimeoutRef.current
      );
    }

    if (shouldShowButton) {
      scrollButtonHideTimeoutRef.current =
        setTimeout(() => {
          setShowScrollBottom(false);
        }, 2500);
    }
  };

  useEffect(() => {
    return () => {
      if (
        scrollButtonHideTimeoutRef.current
      ) {
        clearTimeout(
          scrollButtonHideTimeoutRef.current
        );
      }

      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  const handleAttachFileClick = (
    mode: UploadMode = 'file'
  ) => {
    if (!fileInputRef.current) {
      return;
    }

    fileInputRef.current.accept =
      mode === 'photo'
        ? 'image/png,image/jpeg,image/jpg,image/webp'
        : '.pdf,.doc,.docx,.txt,.csv';

    fileInputRef.current.dataset.uploadMode =
      mode;

    fileInputRef.current.click();
  };

  const handleFileChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const selectedFiles = Array.from(
      event.target.files ?? []
    );

    const uploadMode =
      (event.currentTarget.dataset
        .uploadMode as UploadMode) ||
      'file';

    if (selectedFiles.length > 0) {
      const allowedDocumentExtensions = [
        'pdf',
        'doc',
        'docx',
        'txt',
        'csv',
      ];

      const allowedPhotoTypes = [
        'image/png',
        'image/jpeg',
        'image/jpg',
        'image/webp',
      ];

      const validFiles =
        selectedFiles.filter((file) => {
          const extension =
            file.name
              .split('.')
              .pop()
              ?.toLowerCase() ?? '';

          if (uploadMode === 'photo') {
            return allowedPhotoTypes.includes(
              file.type
            );
          }

          return allowedDocumentExtensions.includes(
            extension
          );
        });

      if (
        validFiles.length !==
        selectedFiles.length
      ) {
        alert(
          uploadMode === 'photo'
            ? 'Upload Foto hanya menerima PNG, JPG, JPEG, atau WEBP.'
            : 'Upload File hanya menerima PDF, DOC, DOCX, TXT, atau CSV.'
        );
      }

      if (validFiles.length > 0) {
        const newFiles =
          validFiles.map((file) => ({
            name: file.name,
            size: file.size,
            type: file.type,
            file,
          }));

        setAttachedFiles(
          (previousFiles) => [
            ...previousFiles,
            ...newFiles,
          ]
        );

        if (isFirstMessage) {
          setIsFirstMessage(false);
        }
      }
    }

    event.target.value = '';
  };

  const handleMicClick = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any)
        .webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert(
        'Maaf, browser Anda tidak mendukung fitur mikrofon. Harap gunakan Google Chrome atau Edge.'
      );

      return;
    }

    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
      return;
    }

    setIsRecording(true);

    if (isFirstMessage) {
      setIsFirstMessage(false);
    }

    const recognition =
      new SpeechRecognition();

    recognition.lang =
      detectedLanguage === 'EN'
        ? 'en-US'
        : 'id-ID';

    recognition.continuous = true;
    recognition.interimResults = true;

    const baseText = inputValue;

    recognition.onresult = (
      event: any
    ) => {
      let transcript = '';

      for (
        let index = event.resultIndex;
        index < event.results.length;
        index += 1
      ) {
        transcript +=
          event.results[index][0]
            .transcript;
      }

      setInputValue(
        baseText +
          (baseText ? ' ' : '') +
          transcript
      );
    };

    recognition.onerror = (
      event: any
    ) => {
      console.error(
        'Error mikrofon:',
        event.error
      );

      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognitionRef.current =
      recognition;

    recognition.start();
  };

  const handleLanguageChange = (
    language: DetectedLanguage
  ) => {
    setDetectedLanguage(language);
    setLanguage(language);
  };

  const handleSendMessage = async (
    text = inputValue,
    files = attachedFiles
  ) => {
    if (isGenerating) {
      stopGenerating();

      setMessages(
        (previousMessages) => [
          ...previousMessages,
          {
            id: `stopped-${Date.now()}`,
            role: 'system',
            content:
              '[ Generation Stopped by User ]',
          },
        ]
      );

      return;
    }

    if (
      !text.trim() &&
      files.length === 0
    ) {
      return;
    }

    if (isFirstMessage) {
      setIsFirstMessage(false);
    }

    setInputValue('');
    setAttachedFiles([]);

    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
    }

    await sendMessage(
      text,
      files,
      detectedLanguage
    );
  };

  const handleClearChat = () => {
    const shouldClear =
      window.confirm(
        'Hapus seluruh riwayat obrolan di layar?'
      );

    if (!shouldClear) {
      return;
    }

    clearChat();
    setInputValue('');
    setAttachedFiles([]);
    setIsFirstMessage(true);
    setShowScrollBottom(false);

    if (
      isRecording &&
      recognitionRef.current
    ) {
      recognitionRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleNewChat = () => {
    clearChat();
    setInputValue('');
    setAttachedFiles([]);
    setIsFirstMessage(true);
    setShowScrollBottom(false);
    setSidebarOpen(false);

    if (
      isRecording &&
      recognitionRef.current
    ) {
      recognitionRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleSelectConversation =
    async (
      selectedConversationId: string
    ) => {
      const normalizedConversationId =
        selectedConversationId.trim();

      if (!normalizedConversationId) {
        setIsFirstMessage(false);
        setSidebarOpen(false);

        setMessages(
          (previousMessages) => [
            ...previousMessages,
            {
              id: `invalid-conversation-${Date.now()}`,
              role: 'system',
              content:
                'ID percakapan tidak valid. Riwayat tidak bisa dibuka.',
            },
          ]
        );

        return;
      }

      setInputValue('');
      setAttachedFiles([]);
      setShowScrollBottom(false);
      setSidebarOpen(false);
      setIsFirstMessage(false);

      if (
        isRecording &&
        recognitionRef.current
      ) {
        recognitionRef.current.stop();
        setIsRecording(false);
      }

      const openedConversation =
        await loadConversation(
          normalizedConversationId
        );

      if (!openedConversation) {
        setIsFirstMessage(false);

        window.setTimeout(() => {
          scrollToBottom();
        }, 100);

        return;
      }

      const conversationLanguage =
        openedConversation.conversation.language;

      if (
        conversationLanguage === 'ID' ||
        conversationLanguage === 'EN'
      ) {
        setDetectedLanguage(conversationLanguage);
        setLanguage(conversationLanguage);
      }

      window.setTimeout(() => {
        scrollToBottom();
      }, 100);
    };

  const handleCopyMessage = async (
    content: string
  ) => {
    try {
      await navigator.clipboard.writeText(
        content
      );

      window.alert(
        'Teks jawaban berhasil disalin!'
      );
    } catch {
      window.alert(
        'Teks jawaban gagal disalin.'
      );
    }
  };

  return (
    <div
      className="flex relative overflow-hidden bg-black"
      style={{
        height: 'var(--app-height)',
      }}
    >
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        multiple
        accept=".pdf,.doc,.docx,.txt,.csv"
        data-upload-mode="file"
        onChange={handleFileChange}
      />

      <Sidebar
        isOpen={sidebarOpen}
        onClose={() =>
          setSidebarOpen(false)
        }
        onNewChat={handleNewChat}
        onSelectConversation={
          handleSelectConversation
        }
      />

      <main className="flex-1 flex flex-col h-full w-full relative min-w-0 overflow-hidden bg-transparent">
        <div
          className={`absolute inset-0 pointer-events-none z-0 transition-opacity duration-[3500ms] ease-in-out ${
            isFirstMessage
              ? 'opacity-100'
              : 'opacity-0'
          }`}
          style={{
            background:
              'radial-gradient(ellipse 34% 30% at 50% 50%, rgba(37, 99, 235, 0.26) 0%, rgba(30, 64, 175, 0.14) 36%, rgba(0, 0, 0, 0) 76%)',
          }}
        />

        <Header
          isOpen={sidebarOpen}
          onToggleSidebar={() =>
            setSidebarOpen(
              (previousState) =>
                !previousState
            )
          }
          detectedLanguage={
            detectedLanguage
          }
          onLanguageChange={
            handleLanguageChange
          }
        />

        {!isFirstMessage &&
          messages.length > 0 && (
            <button
              type="button"
              onClick={scrollToBottom}
              className={`absolute bottom-[calc(5rem+env(safe-area-inset-bottom))] md:bottom-24 right-4 md:right-8 bg-surface-container-high border border-outline-variant rounded-full p-2 text-on-surface-variant hover:text-primary hover:bg-surface-variant shadow-lg z-30 transition-all duration-300 ${
                showScrollBottom
                  ? 'opacity-100 translate-y-0 scale-100'
                  : 'opacity-0 translate-y-3 scale-95 pointer-events-none'
              }`}
              aria-label="Scroll to latest message"
              title="Scroll to latest message"
            >
              <span className="material-symbols-outlined text-xl">
                arrow_downward
              </span>
            </button>
          )}

        <div
          ref={chatContainerRef}
          onScroll={handleScroll}
          className={`flex-1 overflow-y-auto custom-scrollbar transition-all duration-300 relative z-10 flex flex-col ${
            isFirstMessage
              ? 'p-0'
              : 'p-4 md:p-6 pb-[calc(10rem+env(safe-area-inset-bottom))] md:pb-32'
          }`}
        >
          {isFirstMessage ? (
            <WelcomeScreen
              onSendMessage={
                handleSendMessage
              }
              onAttachFileClick={
                handleAttachFileClick
              }
              onMicClick={
                handleMicClick
              }
            />
          ) : (
            <div className="w-full max-w-4xl mx-auto flex flex-col gap-4 md:gap-6 relative z-10 pb-6 animate-fadeIn">
              {messages.map(
                (message) => (
                  <div
                    key={message.id}
                    className={`flex ${
                      message.role ===
                      'user'
                        ? 'justify-end'
                        : 'justify-start'
                    } animate-fadeIn`}
                  >
                    {message.role ===
                    'system' ? (
                      <div className="flex justify-center my-2 text-[9px] md:text-[10px] font-mono text-error/80 border border-error/20 bg-error/5 px-3 py-1 rounded-full mx-auto w-fit">
                        {message.content}
                      </div>
                    ) : message.role ===
                      'user' ? (
                      <div className="max-w-[90%] md:max-w-[80%] bg-surface-variant text-on-surface p-3 md:p-4 rounded-2xl rounded-tr-sm shadow-sm border border-outline-variant">
                        {message.attachments &&
                          message.attachments
                            .length > 0 && (
                            <div className="flex flex-wrap gap-1 mb-2">
                              {message.attachments.map(
                                (
                                  file,
                                  index
                                ) => (
                                  <span
                                    key={`${file.name}-${index}`}
                                    className="bg-surface-container-high text-primary px-2 py-1 rounded text-[9px] md:text-[10px] font-mono border border-outline-variant flex items-center gap-1"
                                  >
                                    <span className="material-symbols-outlined text-[10px] md:text-[12px]">
                                      description
                                    </span>
                                    {file.name}
                                  </span>
                                )
                              )}
                            </div>
                          )}

                        <p className="text-[13px] md:text-sm whitespace-pre-wrap">
                          {message.content}
                        </p>

                        <div className="mt-1.5 md:mt-2 text-[9px] md:text-[10px] text-on-surface-variant text-right font-mono">
                          {message.time}
                        </div>
                      </div>
                    ) : (
                      <div className="max-w-[95%] sm:max-w-[82%] bg-transparent p-0 rounded-none border-none shadow-none">
                        <div className="flex items-center gap-1.5 md:gap-2 mb-2 md:mb-3">
                          <img
                            src="/icon-ungu.png"
                            alt="Assistant Logo"
                            className="h-20 md:h-24 w-auto object-contain"
                          />
                        </div>

                        <TypewriterMarkdown
                          content={
                            message.content
                          }
                          animate={
                            message.shouldAnimate === true
                          }
                          onTick={
                            scrollToBottom
                          }
                          onDone={() => {
                            setMessages(
                              (previousMessages) =>
                                previousMessages.map(
                                  (item) =>
                                    item.id ===
                                    message.id
                                      ? {
                                          ...item,
                                          shouldAnimate:
                                            false,
                                        }
                                      : item
                                )
                            );
                          }}
                        />

                        <div className="mt-5 md:mt-6 pt-3 md:pt-4 border-t border-white/15 flex flex-col sm:flex-row sm:items-center justify-between gap-3 md:gap-4 text-white/70">
                          <div className="flex items-center gap-2 self-start sm:self-auto min-w-0">
                            <span className="material-symbols-outlined text-[14px] md:text-[16px] text-white/70">
                              description
                            </span>

                            <span className="text-[10px] md:text-[11px] font-mono truncate max-w-[180px] md:max-w-full">
                              {
                                message.source
                              }

                              <span className="text-white/45 ml-1">
                                • p.{' '}
                                {message.page ??
                                  '-'}
                              </span>
                            </span>
                          </div>

                          <div className="flex items-center justify-between sm:justify-end gap-4 md:gap-5 w-full sm:w-auto">
                            <span className="text-[10px] md:text-[11px] font-mono text-white/65">
                              Similarity:{' '}

                              <span className="text-white font-semibold">
                                {
                                  message.confidence
                                }
                                %
                              </span>
                            </span>

                            <button
                              type="button"
                              onClick={() =>
                                handleCopyMessage(
                                  message.content
                                )
                              }
                              className="material-symbols-outlined text-[15px] md:text-[17px] text-white/55 hover:text-white transition-colors"
                              title="Salin Teks"
                              aria-label="Salin teks"
                            >
                              content_copy
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )
              )}

              {isGenerating && (
                <div className="flex justify-start animate-fadeIn">
                  <p className="font-mono text-[11px] md:text-xs text-primary/80 tracking-wider animate-pulse">
                    Berpikir...
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {!isFirstMessage && (
          <ChatFooter
            inputValue={inputValue}
            setInputValue={
              setInputValue
            }
            attachedFiles={
              attachedFiles
            }
            onRemoveAttachment={(
              index
            ) =>
              setAttachedFiles(
                (previousFiles) =>
                  previousFiles.filter(
                    (
                      _,
                      fileIndex
                    ) =>
                      fileIndex !==
                      index
                  )
              )
            }
            onAttachFileClick={
              handleAttachFileClick
            }
            onMicClick={
              handleMicClick
            }
            isRecording={
              isRecording
            }
            isGenerating={
              isGenerating
            }
            onSendMessage={() =>
              handleSendMessage(
                inputValue,
                attachedFiles
              )
            }
            onClearChat={
              handleClearChat
            }
          />
        )}
      </main>
    </div>
  );
};