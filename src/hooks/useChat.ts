import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

import type {
  AttachedFile,
  Message,
} from '../types';

import {
  convertChatResponseToMessage,
  sendChatMessage,
} from '../services/chatService';

import type {
  ChatLanguage,
} from '../services/chatService';

import {
  conversationService,
} from '../services/conversationService';

import {
  ApiError,
  getFriendlyApiErrorMessage,
} from '../services/api';

import type {
  ConversationDetail,
  ConversationMessage,
} from '../services/conversationService';

interface UseChatOptions {
  initialMessages?: Message[];
  initialConversationId?: string;
  initialLanguage?: ChatLanguage;
}

function createLocalId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID();
  }

  return `local-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}

function getCurrentTime(): string {
  return new Intl.DateTimeFormat('id-ID', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date());
}

function buildSystemErrorMessage(error: unknown): string {
  const friendlyMessage = getFriendlyApiErrorMessage(error);

  if (!(error instanceof ApiError)) {
    return friendlyMessage;
  }

  if (error.code === 'RAG_NO_CONTEXT') {
    return friendlyMessage;
  }

  if (error.code === 'AI_PROVIDER_ERROR') {
    return friendlyMessage;
  }

  if (error.code === 'RATE_LIMITED') {
    return friendlyMessage;
  }

  if (error.code === 'AUTH_EXPIRED') {
    return friendlyMessage;
  }

  if (error.status === 404) {
    return friendlyMessage;
  }

  if (error.status >= 500) {
    return friendlyMessage;
  }

  return friendlyMessage;
}


function toDisplayConfidence(
  value?: number | null
): number | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return undefined;
  }

  const percent = value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(percent)));
}

function mapConversationMessageToMessage(
  message: ConversationMessage
): Message {
  const role =
    message.role === 'assistant'
      ? 'ai'
      : message.role === 'ai' ||
          message.role === 'user' ||
          message.role === 'system'
        ? message.role
        : 'system';

  const createdAt = message.created_at
    ? new Date(message.created_at)
    : new Date();

  const time = Number.isNaN(createdAt.getTime())
    ? getCurrentTime()
    : new Intl.DateTimeFormat('id-ID', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(createdAt);

  return {
    id: message.id,
    role,
    content: message.content,
    time,
    confidence:
      toDisplayConfidence(message.confidence),
    source:
      typeof message.metadata?.source === 'string'
        ? message.metadata.source
        : undefined,
    page:
      typeof message.metadata?.page === 'string' ||
      typeof message.metadata?.page === 'number'
        ? message.metadata.page
        : undefined,
    shouldAnimate: false,
  };
}

export function useChat(
  options: UseChatOptions = {}
) {
  const {
    initialMessages = [],
    initialConversationId,
    initialLanguage = 'ID',
  } = options;

  const [messages, setMessages] =
    useState<Message[]>(initialMessages);

  const [conversationId, setConversationId] =
    useState<string | undefined>(
      initialConversationId
    );

  const [language, setLanguage] =
    useState<ChatLanguage>(initialLanguage);

  const [isGenerating, setIsGenerating] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const abortControllerRef =
    useRef<AbortController | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const sendMessage = useCallback(
    async (
      content: string,
      attachments: AttachedFile[] = [],
      languageOverride?: ChatLanguage
    ): Promise<boolean> => {
      const normalizedContent = content.trim();

      if (
        !normalizedContent &&
        attachments.length === 0
      ) {
        return false;
      }

      if (isGenerating) {
        return false;
      }

      abortControllerRef.current?.abort();

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const selectedLanguage =
        languageOverride ?? language;

      setLanguage(selectedLanguage);

      const userMessage: Message = {
        id: createLocalId(),
        role: 'user',
        content: normalizedContent,
        time: getCurrentTime(),
        attachments:
          attachments.length > 0
            ? attachments
            : undefined,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        userMessage,
      ]);

      setIsGenerating(true);
      setError(null);

      try {
        const response = await sendChatMessage(
          {
            message: normalizedContent,
            conversationId,
            language: selectedLanguage,
            attachments,
          },
          controller.signal
        );

        const assistantMessage = {
          ...convertChatResponseToMessage(response),
          shouldAnimate: true,
        };

        assistantMessage.time = getCurrentTime();

        if (response.language === 'ID' || response.language === 'EN') {
          setLanguage(response.language);
        }

        setConversationId(response.conversationId);

        setMessages((currentMessages) => [
          ...currentMessages,
          assistantMessage,
        ]);

        window.dispatchEvent(
          new Event('lapisai:conversations-changed')
        );

        return true;
      } catch (caughtError) {
        if (
          caughtError instanceof DOMException &&
          caughtError.name === 'AbortError'
        ) {
          return false;
        }

        const message =
          buildSystemErrorMessage(caughtError);

        setError(message);

        setMessages((currentMessages) => [
          ...currentMessages,
          {
            id: createLocalId(),
            role: 'system',
            content: message,
            time: getCurrentTime(),
          },
        ]);

        return false;
      } finally {
        if (
          abortControllerRef.current === controller
        ) {
          abortControllerRef.current = null;
          setIsGenerating(false);
        }
      }
    },
    [conversationId, isGenerating, language]
  );

  const loadConversation = useCallback(
    async (
      selectedConversationId: string
    ): Promise<ConversationDetail | null> => {
      const normalizedConversationId =
        selectedConversationId.trim();

      if (!normalizedConversationId) {
        return null;
      }

      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      setIsGenerating(false);
      setError(null);

      try {
        const detail =
          await conversationService.detail(
            normalizedConversationId
          );

        setConversationId(
          detail.conversation.id
        );

        if (
          detail.conversation.language === 'ID' ||
          detail.conversation.language === 'EN'
        ) {
          setLanguage(detail.conversation.language);
        }

        setMessages(
          detail.messages.map(
            mapConversationMessageToMessage
          )
        );

        return detail;
      } catch (caughtError) {
        const message =
          buildSystemErrorMessage(caughtError);

        console.error(
          'Gagal membuka percakapan:',
          caughtError
        );

        setError(message);

        setMessages((currentMessages) => [
          ...currentMessages,
          {
            id: createLocalId(),
            role: 'system',
            content: `Gagal membuka percakapan: ${message}`,
            time: getCurrentTime(),
          },
        ]);

        return null;
      }
    },
    []
  );

  const stopGenerating = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsGenerating(false);
  }, []);

  const clearChat = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setMessages([]);
    setConversationId(undefined);
    setIsGenerating(false);
    setError(null);
  }, []);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  return {
    messages,
    setMessages,
    conversationId,
    language,
    setLanguage,
    isGenerating,
    error,
    clearError,
    sendMessage,
    loadConversation,
    stopGenerating,
    clearChat,
  };
}