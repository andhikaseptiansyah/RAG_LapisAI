import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

import type {
  AttachedFile,
  Message,
  MessageSource,
} from './types';

import { useChat } from './hooks/useChat';
import { sanitizeMarkdown } from './utils/sanitizeMarkdown';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { WelcomeScreen } from './components/WelcomeScreen';
import { ChatFooter } from './components/ChatFooter';

// UI VERSION: ANSWER + STRUCTURED CITATIONS + CONFIDENCE
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
  source: MessageSource
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
    labels.push(`Page ${source.page}`);
  }

  const chapter =
    source.chapter ?? source.section;
  if (chapter) {
    labels.push(`Chapter: ${chapter}`);
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
        ? `Paragraph ${source.paragraphStart}`
        : `Paragraphs ${source.paragraphStart}–${paragraphEnd}`
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

  // Retrieval may use more candidates, but the chat UI intentionally
  // shows no more than two citations so the answer remains compact.
  const visibleSources = [...sources]
    .sort(
      (first, second) =>
        (second.relevanceScore ?? 0) -
        (first.relevanceScore ?? 0)
    )
    .slice(0, 2);

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
      aria-label="Answer sources"
    >
      <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-white md:text-[13px]">
        Sources
      </p>

      <div className="mt-3 grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
        {visibleSources.map(
          (source, index) => {
            const locationLabels =
              getSourceLocationLabels(
                source
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
                          Relevance {sourceMatch}%
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
            Confidence: {confidenceLevel} ({confidence}%)
          </p>
        )}
    </section>
  );
};


const GENERAL_THINKING_PHRASES = [
  'Understanding your question...',
  'Reviewing the context...',
  'Preparing the answer...',
];

const DOCUMENT_THINKING_PHRASES = [
  'Reading the document...',
  'Finding the relevant section...',
  'Preparing the answer...',
];

const getCommonPrefixLength = (
  firstText: string,
  secondText: string
) => {
  let prefixLength = 0;

  while (
    prefixLength < firstText.length &&
    prefixLength < secondText.length &&
    firstText[prefixLength] ===
      secondText[prefixLength]
  ) {
    prefixLength += 1;
  }

  return prefixLength;
};

const getTypingDelay = (
  nextCharacter: string,
  isDeleting: boolean
) => {
  if (isDeleting) {
    return 20 + Math.floor(Math.random() * 18);
  }

  if (
    nextCharacter === '.' ||
    nextCharacter === ','
  ) {
    return 120 + Math.floor(Math.random() * 90);
  }

  return 30 + Math.floor(Math.random() * 36);
};

const ThinkingIndicator: React.FC<{
  active: boolean;
  hasAttachments?: boolean;
}> = ({
  active,
  hasAttachments = false,
}) => {
  const phrases = hasAttachments
    ? DOCUMENT_THINKING_PHRASES
    : GENERAL_THINKING_PHRASES;

  const [phraseIndex, setPhraseIndex] =
    useState(0);

  const [visibleText, setVisibleText] =
    useState('');

  const [isDeleting, setIsDeleting] =
    useState(false);

  const [isMounted, setIsMounted] =
    useState(active);

  const [isFadingOut, setIsFadingOut] =
    useState(false);

  const previousActiveRef =
    useRef(active);

  useEffect(() => {
    if (
      active &&
      !previousActiveRef.current
    ) {
      setPhraseIndex(0);
      setVisibleText('');
      setIsDeleting(false);
    }

    previousActiveRef.current = active;
  }, [active]);

  useEffect(() => {
    if (active) {
      setIsMounted(true);
      setIsFadingOut(false);
      return;
    }

    if (!isMounted) {
      return;
    }

    setIsFadingOut(true);

    const hideTimeout = window.setTimeout(
      () => {
        setIsMounted(false);
        setIsFadingOut(false);
      },
      220
    );

    return () => {
      window.clearTimeout(hideTimeout);
    };
  }, [active, isMounted]);

  useEffect(() => {
    setPhraseIndex(0);
    setVisibleText('');
    setIsDeleting(false);
  }, [hasAttachments]);

  useEffect(() => {
    if (!active) {
      return;
    }

    const currentPhrase =
      phrases[phraseIndex];

    const nextPhraseIndex =
      (phraseIndex + 1) % phrases.length;

    const nextPhrase =
      phrases[nextPhraseIndex];

    const retainedPrefixLength =
      getCommonPrefixLength(
        currentPhrase,
        nextPhrase
      );

    const isTypingComplete =
      visibleText === currentPhrase;

    const isDeletionComplete =
      isDeleting &&
      visibleText.length <=
        retainedPrefixLength;

    let delay = getTypingDelay(
      currentPhrase[visibleText.length] ?? '',
      isDeleting
    );

    if (!isDeleting && isTypingComplete) {
      delay = 760 + Math.floor(
        Math.random() * 420
      );
    }

    if (isDeletionComplete) {
      delay = 120;
    }

    const animationTimeout =
      window.setTimeout(() => {
        if (
          !isDeleting &&
          isTypingComplete
        ) {
          setIsDeleting(true);
          return;
        }

        if (isDeletionComplete) {
          setPhraseIndex(nextPhraseIndex);
          setIsDeleting(false);
          return;
        }

        setVisibleText((previousText) => {
          if (isDeleting) {
            return currentPhrase.slice(
              0,
              Math.max(
                previousText.length - 1,
                retainedPrefixLength
              )
            );
          }

          return currentPhrase.slice(
            0,
            previousText.length + 1
          );
        });
      }, delay);

    return () => {
      window.clearTimeout(
        animationTimeout
      );
    };
  }, [
    active,
    isDeleting,
    phraseIndex,
    phrases,
    visibleText,
  ]);

  if (!isMounted) {
    return null;
  }

  return (
    <div
      className={`flex justify-start px-1 md:px-2 transition-all duration-200 ease-out ${
        isFadingOut
          ? 'opacity-0 translate-y-1'
          : 'opacity-100 translate-y-0'
      }`}
      aria-live="polite"
      aria-label="AI is preparing an answer"
    >
      <div className="inline-flex min-h-6 max-w-full items-center text-[15px] md:text-[16px] leading-relaxed tracking-[0.005em] text-zinc-500">
        <span className="block max-w-[86vw] overflow-hidden text-ellipsis whitespace-nowrap md:max-w-[720px]">
          {visibleText}
          <span className="ml-1 inline-block h-[1.05em] w-[6px] rounded-[1px] bg-zinc-600/80 align-[-2px] animate-pulse" />
        </span>
      </div>
    </div>
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
                      <div className="w-full max-w-[96%] sm:max-w-[90%] lg:max-w-[92%]">
                        <div className="flex items-center gap-2 mb-3 md:mb-4 px-1">
                          <img
                            src="/icon-ungu.png"
                            alt="Assistant Logo"
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
                            (message.confidence ?? 0) > 0 && (
                              <p className="mt-3 text-[13px] leading-relaxed text-white/70 md:text-sm">
                                {message.followUpQuestion ? (
                                  <>
                                    <span className="font-medium text-white/85">
                                      {detectedLanguage === 'EN'
                                        ? 'Related question: '
                                        : 'Pertanyaan terkait: '}
                                    </span>
                                    {message.followUpQuestion}
                                  </>
                                ) : detectedLanguage === 'EN' ? (
                                  'I hope this information helps. Please ask another question related to the available company documents.'
                                ) : (
                                  'Semoga informasi ini membantu. Silakan ajukan pertanyaan lain yang berkaitan dengan dokumen perusahaan.'
                                )}
                              </p>
                            )}

                          {message.shouldAnimate !==
                            true && (
                            <CitationPanel
                              message={message}
                            />
                          )}

                          <div className="mt-3 flex justify-end">
                            <button
                              type="button"
                              onClick={() =>
                                handleCopyMessage(
                                  message.content
                                )
                              }
                              className="material-symbols-outlined p-0 text-[19px] text-white/60 transition-colors hover:text-white"
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

              <ThinkingIndicator
                active={isGenerating}
                hasAttachments={Boolean(
                  [...messages]
                    .reverse()
                    .find(
                      (message) =>
                        message.role === 'user'
                    )?.attachments?.length
                )}
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