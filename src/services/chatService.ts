import type {
  AttachedFile,
  Message,
  MessageSource,
} from '../types';

import { apiRequest } from './api';

export type ChatLanguage = 'ID' | 'EN';

export interface SendChatPayload {
  message: string;
  conversationId?: string;
  language?: ChatLanguage;
  model?: string;
  attachments?: AttachedFile[];
}

type RawMessageSource = {
  document_name?: unknown;
  documentName?: unknown;
  document_type?: unknown;
  documentType?: unknown;
  page?: unknown;
  page_is_reliable?: unknown;
  pageIsReliable?: unknown;
  score?: unknown;
  relevanceScore?: unknown;
  relevance_score?: unknown;
  excerpt?: unknown;
  evidence_text?: unknown;
  evidenceText?: unknown;
  chapter?: unknown;
  section?: unknown;
  paragraph_start?: unknown;
  paragraphStart?: unknown;
  paragraph_end?: unknown;
  paragraphEnd?: unknown;
  line_start?: unknown;
  lineStart?: unknown;
  line_end?: unknown;
  lineEnd?: unknown;
};

export interface ChatApiResponse {
  conversationId: string;
  messageId: string;
  answer: string;
  confidence?: number;
  source?: string;
  page?: string | number;
  sources?: RawMessageSource[];
  follow_up_question?: string | null;
  followUpQuestion?: string | null;
  response_time_ms?: number;
  responseTimeMs?: number;
  createdAt?: string;
  language?: ChatLanguage;
  model?: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  language?: ChatLanguage;
  pinned?: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  language?: ChatLanguage;
  pinned?: boolean;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

const hasRealFiles = (
  attachments: AttachedFile[] = []
): boolean => {
  return attachments.some(
    (attachment) =>
      attachment.file instanceof File
  );
};

const buildChatFormData = (
  payload: SendChatPayload
): FormData => {
  const formData = new FormData();

  formData.append(
    'message',
    payload.message
  );

  if (payload.conversationId) {
    formData.append(
      'conversationId',
      payload.conversationId
    );
  }

  if (payload.language) {
    formData.append(
      'language',
      payload.language
    );
  }

  if (payload.model) {
    formData.append(
      'model',
      payload.model
    );
  }

  payload.attachments?.forEach(
    (attachment) => {
      if (
        attachment.file instanceof File
      ) {
        formData.append(
          'files',
          attachment.file,
          attachment.name
        );
      }
    }
  );

  return formData;
};

export const sendChatMessage = async (
  payload: SendChatPayload,
  signal?: AbortSignal
): Promise<ChatApiResponse> => {
  if (
    hasRealFiles(payload.attachments)
  ) {
    return apiRequest<
      ChatApiResponse,
      FormData
    >('/api/chat', {
      method: 'POST',
      body: buildChatFormData(payload),
      signal,
    });
  }

  return apiRequest<
    ChatApiResponse,
    SendChatPayload
  >('/api/chat', {
    method: 'POST',
    body: payload,
    signal,
  });
};

export const getConversations = async (
  signal?: AbortSignal
): Promise<ConversationSummary[]> => {
  return apiRequest<
    ConversationSummary[]
  >('/api/conversations', {
    method: 'GET',
    signal,
  });
};

export const getConversationById =
  async (
    conversationId: string,
    signal?: AbortSignal
  ): Promise<ConversationDetail> => {
    return apiRequest<
      ConversationDetail
    >(
      `/api/conversations/${encodeURIComponent(
        conversationId
      )}`,
      {
        method: 'GET',
        signal,
      }
    );
  };

export const renameConversation =
  async (
    conversationId: string,
    title: string
  ): Promise<ConversationSummary> => {
    return apiRequest<
      ConversationSummary,
      { title: string }
    >(
      `/api/conversations/${encodeURIComponent(
        conversationId
      )}`,
      {
        method: 'PATCH',
        body: {
          title,
        },
      }
    );
  };

export const deleteConversation =
  async (
    conversationId: string
  ): Promise<void> => {
    await apiRequest<null>(
      `/api/conversations/${encodeURIComponent(
        conversationId
      )}`,
      {
        method: 'DELETE',
      }
    );
  };

const toFiniteNumber = (
  value: unknown
): number | undefined => {
  if (
    typeof value !== 'number' ||
    !Number.isFinite(value)
  ) {
    return undefined;
  }

  return value;
};

const toOptionalText = (
  value: unknown
): string | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }

  const normalized = value.trim();
  return normalized || undefined;
};

const toOptionalLocation = (
  value: unknown
): string | number | undefined => {
  if (
    typeof value === 'number' &&
    Number.isFinite(value)
  ) {
    return value;
  }

  if (typeof value === 'string') {
    const normalized = value.trim();

    if (
      normalized &&
      normalized !== '-' &&
      normalized.toLowerCase() !== 'none'
    ) {
      return normalized;
    }
  }

  return undefined;
};

const normalizeScore = (
  value: unknown
): number | undefined => {
  const numericValue = toFiniteNumber(value);

  if (numericValue === undefined) {
    return undefined;
  }

  const normalized =
    numericValue > 1
      ? numericValue / 100
      : numericValue;

  return Math.max(
    0,
    Math.min(1, normalized)
  );
};

export const normalizeMessageSources = (
  value: unknown
): MessageSource[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  const uniqueSources =
    new Map<string, MessageSource>();

  value.forEach((rawValue) => {
    if (
      typeof rawValue !== 'object' ||
      rawValue === null
    ) {
      return;
    }

    const raw =
      rawValue as RawMessageSource;

    const documentName =
      toOptionalText(raw.document_name) ??
      toOptionalText(raw.documentName);

    if (!documentName) {
      return;
    }

    const documentType = (
      toOptionalText(
        raw.document_type ??
        raw.documentType
      ) ??
      documentName.split('.').pop() ??
      ''
    ).toLowerCase();

    const legacyLineStart = toFiniteNumber(
      raw.line_start ?? raw.lineStart
    );
    const legacyLineEnd = toFiniteNumber(
      raw.line_end ?? raw.lineEnd
    );
    const paragraphStart =
      toFiniteNumber(
        raw.paragraph_start ??
        raw.paragraphStart
      );
    const paragraphEnd =
      toFiniteNumber(
        raw.paragraph_end ??
        raw.paragraphEnd
      );

    const rawPageReliability =
      raw.page_is_reliable ??
      raw.pageIsReliable;
    const pageIsReliable =
      typeof rawPageReliability === 'boolean'
        ? rawPageReliability
        : documentType === 'pdf';

    const source: MessageSource = {
      documentName,
      documentType,
      page:
        documentType === 'txt' ||
        (documentType === 'docx' &&
          !pageIsReliable)
          ? undefined
          : toOptionalLocation(raw.page),
      pageIsReliable,
      relevanceScore: normalizeScore(
        raw.relevance_score ??
        raw.score ??
        raw.relevanceScore
      ),
      excerpt: toOptionalText(
        raw.excerpt ??
        raw.evidence_text ??
        raw.evidenceText
      ),
      chapter:
        documentType === 'txt'
          ? undefined
          : toOptionalText(raw.chapter),
      section:
        documentType === 'txt'
          ? undefined
          : toOptionalText(raw.section),
      paragraphStart,
      paragraphEnd,
      lineStart: legacyLineStart,
      lineEnd: legacyLineEnd,
    };

    const dedupeKey = [
      source.documentName.toLowerCase(),
      String(source.documentType ?? ''),
      String(source.page ?? ''),
      String(source.chapter ?? source.section ?? ''),
      String(source.paragraphStart ?? ''),
      String(source.lineStart ?? ''),
    ].join('|');

    const existing =
      uniqueSources.get(dedupeKey);

    if (
      !existing ||
      (source.relevanceScore ?? 0) >
        (existing.relevanceScore ?? 0)
    ) {
      uniqueSources.set(
        dedupeKey,
        source
      );
    }
  });

  return Array.from(
    uniqueSources.values()
  ).sort(
    (first, second) =>
      (second.relevanceScore ?? 0) -
      (first.relevanceScore ?? 0)
  );
};

const toDisplayConfidence = (
  value?: number | null
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

export const convertChatResponseToMessage = (
  response: ChatApiResponse
): Message => {
  const sources =
    normalizeMessageSources(
      response.sources
    );

  const primarySource =
    sources[0];

  return {
    id: response.messageId,
    role: 'ai',
    content: response.answer,
    confidence:
      toDisplayConfidence(
        response.confidence
      ),
    source:
      response.source ??
      primarySource?.documentName,
    page:
      response.page ??
      primarySource?.page,
    sources:
      sources.length > 0
        ? sources
        : undefined,
    responseTimeMs:
      toFiniteNumber(
        response.response_time_ms ??
        response.responseTimeMs
      ),
    followUpQuestion:
      toOptionalText(
        response.follow_up_question ??
        response.followUpQuestion
      ),
  };
};
