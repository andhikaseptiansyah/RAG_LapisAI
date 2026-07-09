import { apiRequest } from './api';

export type ChatLanguage = 'ID' | 'EN';

const isChatLanguage = (
  value: unknown
): value is ChatLanguage => {
  return value === 'ID' || value === 'EN';
};

export type ConversationSummary = {
  id: string;
  title: string;
  language?: ChatLanguage;
  is_pinned?: boolean;
  pinned?: boolean;
  last_message?: string;
  last_user_message?: string;
  last_message_at?: string;
  created_at?: string;
  updated_at?: string;
};

export type ConversationMessage = {
  id: string;
  conversation_id?: string;
  role: 'user' | 'assistant' | 'system' | 'ai' | string;
  content: string;
  attachments?: unknown[];
  confidence?: number | null;
  model_name?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type ConversationDetail = {
  conversation: ConversationSummary;
  messages: ConversationMessage[];
};

export type UpdateConversationInput = {
  title?: string;
  is_pinned?: boolean;
  language?: ChatLanguage;
};

type DeleteResponse = {
  message?: string;
  data?: unknown;
};

const isObject = (
  value: unknown
): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null;
};

const unwrapResponse = (response: unknown): unknown => {
  let current = response;

  for (let index = 0; index < 5; index += 1) {
    if (!isObject(current)) {
      return current;
    }

    if ('data' in current && current.data !== undefined) {
      current = current.data;
      continue;
    }

    if ('result' in current && current.result !== undefined) {
      current = current.result;
      continue;
    }

    if ('payload' in current && current.payload !== undefined) {
      current = current.payload;
      continue;
    }

    return current;
  }

  return current;
};

const normalizeConversationSummary = (
  value: unknown
): ConversationSummary | null => {
  if (!isObject(value)) {
    return null;
  }

  const id =
    typeof value.id === 'string'
      ? value.id
      : '';

  if (!id) {
    return null;
  }

  return {
    id,
    title:
      typeof value.title === 'string'
        ? value.title
        : '',
    language: isChatLanguage(value.language)
      ? value.language
      : undefined,
    is_pinned:
      typeof value.is_pinned === 'boolean'
        ? value.is_pinned
        : undefined,
    pinned:
      typeof value.pinned === 'boolean'
        ? value.pinned
        : undefined,
    last_message:
      typeof value.last_message === 'string'
        ? value.last_message
        : '',
    last_user_message:
      typeof value.last_user_message === 'string'
        ? value.last_user_message
        : '',
    last_message_at:
      typeof value.last_message_at === 'string'
        ? value.last_message_at
        : undefined,
    created_at:
      typeof value.created_at === 'string'
        ? value.created_at
        : undefined,
    updated_at:
      typeof value.updated_at === 'string'
        ? value.updated_at
        : undefined,
  };
};

const normalizeConversationMessage = (
  value: unknown
): ConversationMessage | null => {
  if (!isObject(value)) {
    return null;
  }

  const id =
    typeof value.id === 'string'
      ? value.id
      : '';

  const content =
    typeof value.content === 'string'
      ? value.content
      : '';

  if (!id) {
    return null;
  }

  return {
    id,
    conversation_id:
      typeof value.conversation_id === 'string'
        ? value.conversation_id
        : undefined,
    role:
      typeof value.role === 'string'
        ? value.role
        : 'system',
    content,
    attachments: Array.isArray(value.attachments)
      ? value.attachments
      : [],
    confidence:
      typeof value.confidence === 'number'
        ? value.confidence
        : null,
    model_name:
      typeof value.model_name === 'string'
        ? value.model_name
        : null,
    metadata: isObject(value.metadata)
      ? value.metadata
      : {},
    created_at:
      typeof value.created_at === 'string'
        ? value.created_at
        : undefined,
  };
};

const normalizeConversationList = (
  response: unknown
): ConversationSummary[] => {
  const payload = unwrapResponse(response);

  if (!Array.isArray(payload)) {
    return [];
  }

  return payload
    .map(normalizeConversationSummary)
    .filter(
      (
        conversation
      ): conversation is ConversationSummary =>
        conversation !== null
    );
};

const findConversationDetailPayload = (
  response: unknown
): unknown => {
  const payload = unwrapResponse(response);

  if (
    isObject(payload) &&
    'conversation' in payload &&
    'messages' in payload
  ) {
    return payload;
  }

  if (
    isObject(payload) &&
    'data' in payload
  ) {
    return findConversationDetailPayload(payload.data);
  }

  if (
    isObject(payload) &&
    'detail' in payload
  ) {
    return findConversationDetailPayload(payload.detail);
  }

  if (
    isObject(payload) &&
    'conversationDetail' in payload
  ) {
    return findConversationDetailPayload(
      payload.conversationDetail
    );
  }

  return payload;
};

const normalizeConversationDetail = (
  response: unknown
): ConversationDetail => {
  const payload =
    findConversationDetailPayload(response);

  if (!isObject(payload)) {
    console.error(
      'Response detail percakapan tidak valid:',
      response
    );

    throw new Error(
      'Response detail percakapan tidak valid.'
    );
  }

  const conversation =
    normalizeConversationSummary(payload.conversation);

  const rawMessages = Array.isArray(payload.messages)
    ? payload.messages
    : [];

  const messages = rawMessages
    .map(normalizeConversationMessage)
    .filter(
      (
        message
      ): message is ConversationMessage =>
        message !== null
    );

  if (!conversation) {
    console.error(
      'Response detail percakapan tidak punya conversation valid:',
      response
    );

    throw new Error(
      'Response detail percakapan tidak valid.'
    );
  }

  return {
    conversation,
    messages,
  };
};

export const conversationService = {
  async list(): Promise<ConversationSummary[]> {
    const response = await apiRequest<unknown>(
      '/api/conversations',
      {
        method: 'GET',
      }
    );

    return normalizeConversationList(response);
  },

  async detail(
    conversationId: string
  ): Promise<ConversationDetail> {
    const response = await apiRequest<unknown>(
      `/api/conversations/${conversationId}`,
      {
        method: 'GET',
      }
    );

    return normalizeConversationDetail(response);
  },

  async update(
    conversationId: string,
    input: UpdateConversationInput
  ): Promise<ConversationSummary> {
    const response = await apiRequest<unknown, UpdateConversationInput>(
      `/api/conversations/${conversationId}`,
      {
        method: 'PATCH',
        body: input,
      }
    );

    const payload = unwrapResponse(response);
    const conversation = normalizeConversationSummary(payload);

    if (!conversation) {
      console.error(
        'Response update percakapan tidak valid:',
        response
      );

      throw new Error(
        'Response update percakapan tidak valid.'
      );
    }

    return conversation;
  },

  async rename(
    conversationId: string,
    title: string
  ): Promise<ConversationSummary> {
    return this.update(conversationId, {
      title,
    });
  },

  async setPinned(
    conversationId: string,
    isPinned: boolean
  ): Promise<ConversationSummary> {
    return this.update(conversationId, {
      is_pinned: isPinned,
    });
  },


  async setLanguage(
    conversationId: string,
    language: ChatLanguage
  ): Promise<ConversationSummary> {
    return this.update(conversationId, {
      language,
    });
  },

  async remove(
    conversationId: string
  ): Promise<DeleteResponse> {
    return apiRequest<DeleteResponse>(
      `/api/conversations/${conversationId}`,
      {
        method: 'DELETE',
      }
    );
  },
};
