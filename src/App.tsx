import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  AnimatePresence,
  motion,
  useReducedMotion,
} from 'framer-motion';

import type {
  AttachedFile,
  Message,
  MessageSource,
} from './types';

import { useChat } from './hooks/useChat';
import type { ChatProgressEvent } from './services/chatService';
import { sanitizeMarkdown } from './utils/sanitizeMarkdown';
import { Sidebar } from './components/Sidebar';
import { ConversationNavigatorPanel } from './components/ConversationNavigatorPanel';
import { Header } from './components/Header';
import { WelcomeScreen } from './components/WelcomeScreen';
import { ChatFooter } from './components/ChatFooter';
import { TTSButton } from './components/TTSButton'; // <-- IMPORT BARU TTS
import {
  useUiLanguage,
  type UiLanguage,
} from './i18n/LanguageContext';

// UI VERSION: ANSWER + STRUCTURED CITATIONS + CONFIDENCE
type DetectedLanguage = UiLanguage;
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
        className="prose prose-invert prose-custom max-w-none text-white text-[15px] md:text-[17px] leading-[1.75] tracking-[0.005em] [&_p]:text-white [&_li]:text-white [&_strong]:text-white [&_em]:text-white [&_h1]:text-white [&_h2]:text-white [&_h3]:text-white [&_h4]:text-white [&_a]:text-white [&_blockquote]:text-white [&_code]:text-white"
        dangerouslySetInnerHTML={{
          __html:
            sanitizeMarkdown(visibleText),
        }}
      />

      {!isDone && (
        <span className="inline-block w-1.5 h-5 ml-1 bg-white/80 animate-pulse align-middle" />
      )}
    </>
  );
};


const toPercent = (
  value?: number
): number | undefined => {
  if (
    typeof value !== 'number' ||
    !Number.isFinite(value)
  ) {
    return undefined;
  }

  const percent =
    value <= 1
      ? value * 100
      : value;

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(percent)
    )
  );
};

const getSourceLocationLabels = (
  source: MessageSource,
  language: UiLanguage
): string[] => {
  const labels: string[] = [];
  const documentType = (
    source.documentType ??
    source.documentName.split('.').pop() ??
    ''
  ).toLowerCase();

  const mayShowPage =
    documentType === 'pdf' ||
    (documentType === 'docx' &&
      source.pageIsReliable === true) ||
    !['pdf', 'docx', 'txt'].includes(
      documentType
    );

  if (
    mayShowPage &&
    source.page !== undefined &&
    source.page !== null &&
    String(source.page).trim() !== ''
  ) {
    labels.push(
      `${language === 'EN' ? 'Page' : 'Halaman'} ${source.page}`
    );
  }

  const chapter =
    source.chapter ?? source.section;
  if (chapter && documentType !== 'txt') {
    labels.push(
      `${language === 'EN' ? 'Chapter' : 'Bab'}: ${chapter}`
    );
  }

  if (
    source.paragraphStart !== undefined
  ) {
    const paragraphEnd =
      source.paragraphEnd ??
      source.paragraphStart;

    labels.push(
      paragraphEnd ===
        source.paragraphStart
        ? `${language === 'EN' ? 'Paragraph' : 'Paragraf'} ${source.paragraphStart}`
        : `${language === 'EN' ? 'Paragraphs' : 'Paragraf'} ${source.paragraphStart}–${paragraphEnd}`
    );
  }

  return labels;
};

const getConfidenceLevel = (
  confidence?: number
): 'High' | 'Medium' | 'Low' | undefined => {
  if (confidence === undefined) {
    return undefined;
  }

  if (confidence >= 85) {
    return 'High';
  }

  if (confidence >= 60) {
    return 'Medium';
  }

  return 'Low';
};

const CitationPanel: React.FC<{
  message: Message;
}> = ({
  message,
}) => {
  const { language, t } = useUiLanguage();
  const [expandedSources, setExpandedSources] =
    useState<Set<number>>(() => new Set());

  const fallbackSource:
    | MessageSource
    | undefined =
    message.source
      ? {
          documentName:
            message.source,
          page: message.page,
        }
      : undefined;

  const sources =
    message.sources &&
    message.sources.length > 0
      ? message.sources
      : fallbackSource
        ? [fallbackSource]
        : [];

  const visibleSources = [...sources]
    .sort(
      (first, second) =>
        (second.relevanceScore ?? 0) -
        (first.relevanceScore ?? 0)
    )
    .slice(0, 3);

  if (visibleSources.length === 0) {
    return null;
  }

  const confidence =
    toPercent(message.confidence);

  const confidenceLevel =
    getConfidenceLevel(confidence);

  const toggleSource = (index: number) => {
    setExpandedSources((current) => {
      const next = new Set(current);

      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }

      return next;
    });
  };

  return (
    <section
      className="mt-5 pt-2 text-white"
      aria-label={t('sources')}
    >
      <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-white md:text-[13px]">
        {t('sources')}
      </p>

      <div className="mt-3 grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
        {visibleSources.map(
          (source, index) => {
            const locationLabels =
              getSourceLocationLabels(
                source,
                language
              );
            const sourceMatch =
              toPercent(
                source.relevanceScore
              );
            const isExpanded =
              expandedSources.has(index);
            const hasExcerpt = Boolean(
              source.excerpt?.trim()
            );

            return (
              <article
                key={`${source.documentName}-${source.page ?? 'no-page'}-${index}`}
                className="min-w-0"
              >
                <button
                  type="button"
                  className="flex w-full items-start justify-between gap-3 text-left"
                  onClick={() =>
                    hasExcerpt &&
                    toggleSource(index)
                  }
                  aria-expanded={
                    hasExcerpt
                      ? isExpanded
                      : undefined
                  }
                  aria-controls={
                    hasExcerpt
                      ? `source-excerpt-${index}`
                      : undefined
                  }
                  disabled={!hasExcerpt}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block break-words text-[13px] font-semibold leading-relaxed text-white md:text-[14px]">
                      {visibleSources.length > 1
                        ? `${index + 1}. ${source.documentName}`
                        : source.documentName}
                    </span>

                    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] leading-relaxed text-white/70 md:text-[12px]">
                      {locationLabels.length > 0 && (
                        <span>
                          {locationLabels.join(' · ')}
                        </span>
                      )}

                      {sourceMatch !== undefined && (
                        <span className="font-medium text-[#AFC7FF]">
                          {language === 'EN' ? 'Relevance' : 'Relevansi'} {sourceMatch}%
                        </span>
                      )}
                    </span>
                  </span>

                  {hasExcerpt && (
                    <svg
                      className={`mt-0.5 h-5 w-5 shrink-0 text-white/75 transition-transform duration-200 ${
                        isExpanded
                          ? 'rotate-180'
                          : ''
                      }`}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="m6 9 6 6 6-6" />
                    </svg>
                  )}
                </button>

                {hasExcerpt && isExpanded && (
                  <p
                    id={`source-excerpt-${index}`}
                    className="mt-2 whitespace-pre-line text-[12px] italic leading-relaxed text-white/85 md:text-[13px]"
                  >
                    “{source.excerpt}”
                  </p>
                )}
              </article>
            );
          }
        )}
      </div>

      {confidence !== undefined &&
        confidenceLevel && (
          <p className="mt-4 text-[12px] font-medium text-white md:text-[13px]">
            {language === 'EN' ? 'Confidence' : 'Keyakinan'}:{' '}
            {language === 'EN'
              ? confidenceLevel
              : confidenceLevel === 'High'
                ? 'Tinggi'
                : confidenceLevel === 'Medium'
                  ? 'Sedang'
                  : 'Rendah'}{' '}
            ({confidence}%)
          </p>
        )}
    </section>
  );
};


const ProgressStatusIcon: React.FC<{
  status: ChatProgressEvent['status'];
}> = ({ status }) => {
  const reduceMotion = useReducedMotion();

  if (status === 'completed') {
    return (
      <motion.span
        initial={reduceMotion ? false : { opacity: 0, scale: 0.72 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-blue-200/45 text-blue-100"
        aria-hidden="true"
      >
        <svg
          className="h-2.5 w-2.5"
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <motion.path
            d="M2.3 6.2 4.7 8.4 9.6 3.4"
            initial={reduceMotion ? false : { pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.28, delay: 0.05, ease: 'easeOut' }}
          />
        </svg>
      </motion.span>
    );
  }

  if (status === 'failed') {
    return (
      <motion.span
        initial={reduceMotion ? false : { opacity: 0, scale: 0.72 }}
        animate={{ opacity: 1, scale: 1 }}
        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-amber-200/45 text-[10px] font-semibold text-amber-100"
        aria-hidden="true"
      >
        !
      </motion.span>
    );
  }

  if (status === 'skipped') {
    return (
      <span
        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-white/15 text-[10px] text-white/35"
        aria-hidden="true"
      >
        –
      </span>
    );
  }

  return (
    <span
      className="relative flex h-4 w-4 shrink-0 items-center justify-center"
      aria-hidden="true"
    >
      <span className="absolute inset-[1px] rounded-full border border-blue-100/20" />
      <span
        className={`absolute inset-[1px] rounded-full border border-transparent border-t-blue-100 border-r-blue-300/70 ${
          reduceMotion ? '' : 'animate-spin'
        }`}
      />
      <span className="h-1 w-1 rounded-full bg-blue-100 shadow-[0_0_7px_rgba(191,219,254,0.9)]" />
    </span>
  );
};

const ProgressIndicator: React.FC<{
  active: boolean;
  events: ChatProgressEvent[];
}> = ({
  active,
  events,
}) => {
  const reduceMotion = useReducedMotion();
  const { language, t } = useUiLanguage();

  if (!active || events.length === 0) {
    return null;
  }

  return (
    <section
      className="mx-1 max-w-[720px] bg-transparent px-1 py-2 md:mx-2 md:px-0"
      aria-live="polite"
      aria-label={t('answerProgress')}
    >
      <div className="mb-2.5 flex items-center justify-between gap-3 border-b border-white/[0.07] pb-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-white/58 md:text-[11px]">
          {t('answerProgress')}
        </p>

        <div className="flex items-center gap-1.5 text-[9px] text-white/35 md:text-[10px]">
          <motion.span
            className="h-1.5 w-1.5 rounded-full bg-blue-200"
            animate={
              reduceMotion
                ? undefined
                : { opacity: [0.35, 1, 0.35], scale: [0.9, 1.15, 0.9] }
            }
            transition={{ duration: 1.7, repeat: Infinity, ease: 'easeInOut' }}
            aria-hidden="true"
          />
          {language === 'EN' ? 'Live backend stages' : 'Tahap backend aktual'}
        </div>
      </div>

      <div className="space-y-2.5">
        <AnimatePresence initial={false}>
          {events.map((event, index) => {
            const isCurrent = event.status === 'active';
            const isLast = index === events.length - 1;

            return (
              <motion.div
                layout
                key={event.step}
                initial={
                  reduceMotion
                    ? false
                    : { opacity: 0, x: -7, y: 3, filter: 'blur(3px)' }
                }
                animate={{
                  opacity: isCurrent ? 1 : 0.82,
                  x: 0,
                  y: 0,
                  filter: 'blur(0px)',
                }}
                exit={
                  reduceMotion
                    ? undefined
                    : { opacity: 0, x: 5, transition: { duration: 0.14 } }
                }
                transition={{ duration: 0.24, ease: 'easeOut' }}
                className="flex items-start gap-2.5"
              >
                <div className="relative flex w-4 shrink-0 justify-center self-stretch pt-0.5">
                  <ProgressStatusIcon status={event.status} />

                  {!isLast && (
                    <motion.span
                      initial={reduceMotion ? false : { scaleY: 0, opacity: 0 }}
                      animate={{ scaleY: 1, opacity: 1 }}
                      transition={{ duration: 0.25, ease: 'easeOut' }}
                      className="absolute bottom-[-0.7rem] top-[1.22rem] w-px origin-top bg-gradient-to-b from-blue-200/30 via-blue-200/12 to-transparent"
                      aria-hidden="true"
                    />
                  )}
                </div>

                <div className="min-w-0 flex-1 pb-0.5">
                  <p
                    className={`text-[12px] font-medium leading-[1.45] md:text-[13px] ${
                      isCurrent
                        ? 'rag-progress-active-title'
                        : event.status === 'failed'
                          ? 'text-amber-100'
                          : 'text-white/78'
                    }`}
                  >
                    {event.title}
                  </p>

                  {event.detail && (
                    <motion.p
                      initial={reduceMotion ? false : { opacity: 0, y: 2 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: 0.04 }}
                      className="mt-0.5 text-[10.5px] leading-[1.5] text-white/43 md:text-[11.5px]"
                    >
                      {event.detail}
                    </motion.p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
};

export const App: React.FC = () => {
  const {
    language: detectedLanguage,
    setLanguage: setUiLanguage,
    t,
  } = useUiLanguage();

  const [isFirstMessage, setIsFirstMessage] =
    useState(true);

  const [sidebarOpen, setSidebarOpen] =
    useState(false);

  const [conversationNavigatorOpen, setConversationNavigatorOpen] =
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
    progressEvents,
    sendMessage,
    loadConversation,
    setLanguage: setChatLanguage,
    model,
    setModel,
    stopGenerating,
    clearChat,
  } = useChat({
    initialLanguage: detectedLanguage,
  });

  useEffect(() => {
    setChatLanguage(detectedLanguage);
  }, [detectedLanguage, setChatLanguage]);

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

  const scrollToMessage = useCallback((messageId: string) => {
    const normalizedMessageId = messageId.trim();

    if (!normalizedMessageId) {
      scrollToBottom();
      return;
    }

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const targetMessage =
          chatContainerRef.current?.querySelector<HTMLElement>(
            `[data-message-id="${normalizedMessageId}"]`
          );

        if (!targetMessage) {
          scrollToBottom();
          return;
        }

        targetMessage.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });

        targetMessage.classList.add(
          'ring-1',
          'ring-primary/60',
          'rounded-2xl'
        );

        window.setTimeout(() => {
          targetMessage.classList.remove(
            'ring-1',
            'ring-primary/60',
            'rounded-2xl'
          );
        }, 1600);
      });
    });
  }, [scrollToBottom]);

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
            ? t('photoFormatError')
            : t('fileFormatError')
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
        t('microphoneUnsupported')
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
        'Kesalahan mikrofon:',
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
    setUiLanguage(language);
    setChatLanguage(language);
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
              t('requestStopped'),
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
        t('clearChatConfirm')
      );

    if (!shouldClear) {
      return;
    }

    // --- KODE UPDATE: Matikan suara & Stop AI saat Hapus Chat ---
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (isGenerating) {
      stopGenerating();
    }
    // ----------------------------------------------------------

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
    // --- KODE UPDATE: Matikan suara & Stop AI saat Chat Baru ---
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (isGenerating) {
      stopGenerating();
    }
    // ---------------------------------------------------------
    
    clearChat();
    setInputValue('');
    setAttachedFiles([]);
    setIsFirstMessage(true);
    setShowScrollBottom(false);
    setSidebarOpen(false);
    setConversationNavigatorOpen(false);

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
      selectedConversationId: string,
      targetMessageId?: string
    ) => {
      const normalizedConversationId =
        selectedConversationId.trim();

      if (!normalizedConversationId) {
        setIsFirstMessage(false);
        setSidebarOpen(false);
        setConversationNavigatorOpen(false);

        setMessages(
          (previousMessages) => [
            ...previousMessages,
            {
              id: `invalid-conversation-${Date.now()}`,
              role: 'system',
              content:
                t('invalidConversation'),
            },
          ]
        );

        return;
      }

      // --- KODE UPDATE: Matikan suara & Stop AI saat pindah riwayat ---
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      if (isGenerating) {
        stopGenerating();
      }
      // --------------------------------------------------------------

      setInputValue('');
      setAttachedFiles([]);
      setShowScrollBottom(false);
      setSidebarOpen(false);
      setConversationNavigatorOpen(false);
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
        setUiLanguage(conversationLanguage);
        setChatLanguage(conversationLanguage);
      }

      window.setTimeout(() => {
        if (targetMessageId) {
          scrollToMessage(targetMessageId);
          return;
        }

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
        t('answerCopied')
      );
    } catch {
      window.alert(
        t('answerCopyFailed')
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
        onToggle={() =>
          setSidebarOpen((previousState) => !previousState)
        }
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
          isSidebarOpen={sidebarOpen}
          isConversationNavigatorOpen={conversationNavigatorOpen}
          onToggleSidebar={() =>
            setSidebarOpen(
              (previousState) => !previousState
            )
          }
          onToggleConversationNavigator={() =>
            setConversationNavigatorOpen(
              (previousState) => !previousState
            )
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
              aria-label={t('scrollLatest')}
              title={t('scrollLatest')}
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
              onMicClick={
                handleMicClick
              }
              language={detectedLanguage}
              model={model}
              onModelChange={setModel}
            />
          ) : (
            <div className="w-full max-w-4xl mx-auto flex flex-col gap-4 md:gap-6 relative z-10 pb-6 animate-fadeIn">
              {messages.map(
                (message) => (
                  <div
                    key={message.id}
                    data-message-id={message.id}
                    className={`flex scroll-mt-24 transition-shadow ${
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
                      <div className="w-full max-w-[96%] sm:max-w-[90%] lg:max-w-[92%]">
                        <div className="flex items-center gap-2 mb-3 md:mb-4 px-1">
                          <img
                            src="/icon-ungu.png"
                            alt="Logo Asisten"
                            className="h-16 md:h-20 w-auto object-contain"
                          />
                        </div>

                        <div className="relative px-1 md:px-2">
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

                          {message.shouldAnimate !== true &&
                            (message.sources?.length ?? 0) > 0 &&
                            (message.confidence ?? 0) > 0 &&
                            message.followUpQuestion && (
                              <p className="mt-3 text-[13px] leading-relaxed text-white/70 md:text-sm">
                                <span className="font-medium text-white/85">
                                  {detectedLanguage === 'EN'
                                    ? 'Related question: '
                                    : 'Pertanyaan terkait: '}
                                </span>
                                {message.followUpQuestion}
                              </p>
                            )}

                          {message.shouldAnimate !==
                            true && (
                            <CitationPanel
                              message={message}
                            />
                          )}

                          {/* --- KODE UPDATE: Menambahkan TTSButton dan menyesuaikan tata letak --- */}
                          <div className="mt-3 flex justify-end gap-3">
                            <TTSButton
                              text={message.content}
                              language={detectedLanguage}
                            />
                            <button
                              type="button"
                              onClick={() =>
                                handleCopyMessage(
                                  message.content
                                )
                              }
                              className="material-symbols-outlined p-0 text-[19px] text-white/60 transition-colors hover:text-white"
                              title={detectedLanguage === 'EN' ? 'Copy text' : 'Salin teks'}
                              aria-label={detectedLanguage === 'EN' ? 'Copy text' : 'Salin teks'}
                            >
                              content_copy
                            </button>
                          </div>
                          {/* ---------------------------------------------------------------------- */}
                        </div>
                      </div>
                    )}
                  </div>
                )
              )}

              <ProgressIndicator
                active={isGenerating}
                events={progressEvents}
              />
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

      <ConversationNavigatorPanel
        isOpen={conversationNavigatorOpen}
        onClose={() => setConversationNavigatorOpen(false)}
        messages={messages}
        detectedLanguage={detectedLanguage}
        onLanguageChange={handleLanguageChange}
        onSelectMessage={scrollToMessage}
      />
    </div>
  );
};
