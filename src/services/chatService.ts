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
  attachments?: AttachedFile[];
}

export interface ChatApiResponse {
  conversationId: string;
  messageId: string;
  answer: string;
  confidence?: number;
  source?: string;
  page?: string | number;
  sources?: MessageSource[];
  createdAt?: string;
  language?: ChatLanguage;
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


const toDisplayConfidence = (
  value?: number | null
): number | undefined => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return undefined;
  }

  const percent = value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(percent)));
};

export const convertChatResponseToMessage = (
  response: ChatApiResponse
): Message => {
  const primarySource =
    response.sources?.[0];

  return {
    id: response.messageId,
    role: 'ai',
    content: response.answer,
    confidence:
      toDisplayConfidence(response.confidence),
    source:
      response.source ??
      primarySource?.documentName,
    page:
      response.page ??
      primarySource?.page,
    sources:
      response.sources,
  };
};
