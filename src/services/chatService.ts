import type {
  AttachedFile,
  Message,
  MessageSource,
} from '../types';

import { ApiError, apiRequest } from './api';
import { clearStoredAuth, getStoredAuthToken } from './authStorage';

export type ChatLanguage = 'ID' | 'EN';

export type ChatProgressStatus =
  | 'active'
  | 'completed'
  | 'skipped'
  | 'failed';

export interface ChatProgressEvent {
  step: string;
  status: ChatProgressStatus;
  title: string;
  detail?: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export type ChatProgressHandler = (
  event: ChatProgressEvent
) => void;

export interface SendChatPayload {
  message: string;
  queryId?: string;
  conversationId?: string;
  language?: ChatLanguage;
  model?: string;
  attachments?: AttachedFile[];
}

export type QueryFailureReason =
  | 'USER_STOPPED'
  | 'CLIENT_ERROR'
  | 'NETWORK_OFFLINE'
  | 'EMPTY_RESPONSE';

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
  generation_mode?: string;
  buildVersion?: string;
  chatServiceSha256?: string;
  retrieval_mode?: string;
  retrieval_query?: string;
  failure_stage?: string | null;
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

  if (payload.queryId) {
    formData.append(
      'queryId',
      payload.queryId
    );
  }

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

const CHAT_API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  'http://127.0.0.1:8000'
).replace(/\/+$/, '');

type StreamEnvelope = {
  event: string;
  data: unknown;
};

const parseSseBlock = (block: string): StreamEnvelope | null => {
  let event = 'message';
  const dataLines: string[] = [];

  block.split('\n').forEach((line) => {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  });

  if (dataLines.length === 0) {
    return null;
  }

  const rawData = dataLines.join('\n');
  try {
    return {
      event,
      data: JSON.parse(rawData) as unknown,
    };
  } catch {
    return { event, data: rawData };
  }
};

const isProgressEvent = (
  value: unknown
): value is ChatProgressEvent => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const candidate = value as Partial<ChatProgressEvent>;
  return (
    typeof candidate.step === 'string' &&
    typeof candidate.title === 'string' &&
    (candidate.status === 'active' ||
      candidate.status === 'completed' ||
      candidate.status === 'skipped' ||
      candidate.status === 'failed')
  );
};

const buildStreamRequestBody = (
  payload: SendChatPayload,
  headers: Headers
): BodyInit => {
  if (hasRealFiles(payload.attachments)) {
    return buildChatFormData(payload);
  }

  headers.set('Content-Type', 'application/json');
  return JSON.stringify(payload);
};

const parseStreamHttpError = async (
  response: Response
): Promise<ApiError> => {
  const rawPayload = await response.text().catch(() => '');
  let payload: unknown = rawPayload || null;
  if (rawPayload) {
    try {
      payload = JSON.parse(rawPayload) as unknown;
    } catch {
      payload = rawPayload;
    }
  }

  const data = (
    typeof payload === 'object' &&
    payload !== null
  )
    ? payload as Record<string, unknown>
    : null;
  const detail = (
    data &&
    typeof data.detail === 'object' &&
    data.detail !== null
  )
    ? data.detail as Record<string, unknown>
    : null;
  const message =
    (typeof data?.message === 'string' && data.message) ||
    (typeof detail?.message === 'string' && detail.message) ||
    (typeof data?.detail === 'string' && data.detail) ||
    `Request failed with status ${response.status}`;
  const code = response.status === 401
    ? 'AUTH_EXPIRED'
    : response.status === 429
      ? 'RATE_LIMITED'
      : response.status >= 500
        ? 'INTERNAL_SERVER_ERROR'
        : 'UNKNOWN_ERROR';

  return new ApiError(
    message,
    response.status,
    payload,
    code
  );
};

export const sendChatMessage = async (
  payload: SendChatPayload,
  signal?: AbortSignal,
  onProgress?: ChatProgressHandler
): Promise<ChatApiResponse> => {
  const headers = new Headers({
    Accept: 'text/event-stream',
  });
  const authToken = getStoredAuthToken();
  if (authToken) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }

  let response: Response;
  try {
    response = await fetch(
      `${CHAT_API_BASE_URL}/api/chat/stream`,
      {
        method: 'POST',
        headers,
        body: buildStreamRequestBody(payload, headers),
        signal,
        credentials: 'include',
      }
    );
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === 'AbortError'
    ) {
      throw error;
    }

    throw new ApiError(
      error instanceof Error
        ? error.message
        : 'Unable to connect to the server.',
      0,
      null,
      'NETWORK_ERROR'
    );
  }

  if (!response.ok) {
    const streamError = await parseStreamHttpError(response);
    if (response.status === 401) {
      clearStoredAuth();
      if (window.location.pathname !== '/login') {
        const currentPath =
          window.location.pathname + window.location.search;
        window.location.href = `/login?redirect=${encodeURIComponent(
          currentPath
        )}`;
      }
    }
    throw streamError;
  }

  if (!response.body) {
    throw new ApiError(
      'Server did not provide a progress stream.',
      500,
      null,
      'INTERNAL_SERVER_ERROR'
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse: ChatApiResponse | null = null;

  const handleEnvelope = (envelope: StreamEnvelope): void => {
    if (envelope.event === 'progress' && isProgressEvent(envelope.data)) {
      onProgress?.(envelope.data);
      return;
    }

    if (envelope.event === 'result') {
      finalResponse = envelope.data as ChatApiResponse;
      return;
    }

    if (envelope.event === 'error') {
      const streamError = (
        typeof envelope.data === 'object' &&
        envelope.data !== null
      )
        ? envelope.data as Record<string, unknown>
        : {};
      throw new ApiError(
        typeof streamError.message === 'string'
          ? streamError.message
          : 'Proses chat gagal.',
        typeof streamError.statusCode === 'number'
          ? streamError.statusCode
          : 500,
        envelope.data,
        streamError.code === 'CHAT_CANCELLED'
          ? 'UNKNOWN_ERROR'
          : 'INTERNAL_SERVER_ERROR'
      );
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, '\n');

    let separatorIndex = buffer.indexOf('\n\n');
    while (separatorIndex >= 0) {
      const block = buffer.slice(0, separatorIndex).trim();
      buffer = buffer.slice(separatorIndex + 2);
      if (block) {
        const envelope = parseSseBlock(block);
        if (envelope) {
          handleEnvelope(envelope);
        }
      }
      separatorIndex = buffer.indexOf('\n\n');
    }
  }

  const trailingBlock = buffer.trim();
  if (trailingBlock) {
    const envelope = parseSseBlock(trailingBlock);
    if (envelope) {
      handleEnvelope(envelope);
    }
  }

  if (!finalResponse) {
    throw new ApiError(
      'Progress stream ended before the answer was received.',
      500,
      null,
      'INTERNAL_SERVER_ERROR'
    );
  }

  const completedResponse = finalResponse as ChatApiResponse;
  if (completedResponse.buildVersion) {
    console.info(
      `[LapisAI] backend build: ${completedResponse.buildVersion}; ` +
      `chatService=${completedResponse.chatServiceSha256 ?? 'unknown'}; ` +
      `retrieval=${completedResponse.retrieval_mode ?? 'unknown'}; ` +
      `failureStage=${completedResponse.failure_stage ?? 'none'}`
    );
  } else {
    console.warn('[LapisAI] backend response has no buildVersion; an older backend may still be active.');
  }

  return completedResponse;
};

export const recordQueryFailure = async (
  queryId: string,
  question: string,
  reason: QueryFailureReason
): Promise<void> => {
  await apiRequest<
    { status: string; queryId: string },
    {
      queryId: string;
      question: string;
      reason: QueryFailureReason;
    }
  >('/api/query-logs/failure', {
    method: 'POST',
    body: {
      queryId,
      question,
      reason,
    },
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
