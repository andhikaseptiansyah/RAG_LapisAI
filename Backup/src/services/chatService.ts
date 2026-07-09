import { randomUUID } from 'node:crypto';

import type {
  PoolClient,
} from 'pg';

import {
  withTransaction,
} from '../config/database.js';

import {
  createConversationForUser,
  deleteConversationByIdForUser,
  findConversationRowByIdAndUser,
  listConversationRowsByUser,
  touchConversation,
  updateConversationLanguageRowForUser,
  updateConversationTitleRowForUser,
} from '../repositories/conversationRepository.js';

import {
  createAssistantMessage,
  createUserMessage,
  listConversationHistoryRows,
  listConversationMessages,
  type MessageRole,
} from '../repositories/messageRepository.js';

import {
  createQueryLog,
} from '../repositories/queryLogRepository.js';

import {
  answerWithRag,
  type RetrievedChunk,
} from './ragService.js';

import type {
  AiMessage,
  AiRole,
} from './aiService.js';

import { AppError, createValidationError } from '../utils/appError.js';

export type ChatLanguage = 'ID' | 'EN';

export interface UploadedFileLike {
  originalname: string;
  mimetype: string;
  size: number;
  filename?: string;
  path?: string;
  buffer?: Buffer;
}

interface ProcessChatInput {
  message: string;
  conversationId?: string;
  language: ChatLanguage;
  files: UploadedFileLike[];
  userId: string;
}

interface MessageSource {
  documentName: string;
  page: string;
  chunkId: string;
  relevanceScore: number;
}

interface ProcessChatResult {
  conversationId: string;
  messageId: string;
  answer: string;
  confidence: number;
  sources: MessageSource[];
  createdAt: string;
  language: ChatLanguage;
}

interface SavedUserMessageResult {
  conversationId: string;
  userMessageId: string;
  language: ChatLanguage;
}

const buildAttachments = (
  files: UploadedFileLike[]
) => {
  return files.map((file) => ({
    name: file.originalname,
    mimeType: file.mimetype,
    size: file.size,
    path:
      file.path ??
      file.filename ??
      null,
  }));
};

const normalizeQuestion = (
  message: string,
  files: UploadedFileLike[]
): string => {
  const trimmedMessage = message.trim();

  if (trimmedMessage) {
    return trimmedMessage;
  }

  if (files.length > 0) {
    return '[Lampiran tanpa teks]';
  }

  return '';
};

const buildAutoConversationTitle = (
  question: string
): string => {
  const normalizedQuestion = question
    .replace(/\s+/g, ' ')
    .replace(/^['"`*_>#\-\s]+/, '')
    .trim();

  if (!normalizedQuestion) {
    return 'Percakapan Baru';
  }

  const maxLength = 72;

  if (normalizedQuestion.length <= maxLength) {
    return normalizedQuestion;
  }

  const sliced = normalizedQuestion.slice(0, maxLength);
  const lastSpaceIndex = sliced.lastIndexOf(' ');

  if (lastSpaceIndex >= 40) {
    return `${sliced.slice(0, lastSpaceIndex).trim()}...`;
  }

  return `${sliced.trim()}...`;
};

const mapDbRoleToAiRole = (
  role: MessageRole
): AiRole => {
  if (role === 'assistant') {
    return 'assistant';
  }

  return role;
};

const getConversationHistory = async (
  conversationId: string,
  currentUserMessageId: string
): Promise<AiMessage[]> => {
  const rows =
    await listConversationHistoryRows(
      conversationId,
      currentUserMessageId,
      8
    );

  return rows
    .reverse()
    .filter((row) => row.content.trim().length > 0)
    .map((row) => ({
      role: mapDbRoleToAiRole(row.role),
      content: row.content,
    }));
};

const mapSources = (
  sources: RetrievedChunk[]
): MessageSource[] => {
  return sources.map((source) => ({
    documentName: source.documentName,
    page: source.page,
    chunkId: source.chunkId,
    relevanceScore: source.score,
  }));
};

const saveUserMessage = async (
  input: ProcessChatInput,
  question: string
): Promise<SavedUserMessageResult> => {
  return withTransaction<SavedUserMessageResult>(
    async (
      client: PoolClient
    ): Promise<SavedUserMessageResult> => {
      let conversationId =
        input.conversationId;

      let effectiveLanguage = input.language;

      if (conversationId) {
        const existingConversation =
          await findConversationRowByIdAndUser(
            conversationId,
            input.userId,
            client
          );

        if (!existingConversation) {
          throw new AppError({
            code: 'CONVERSATION_NOT_FOUND',
            statusCode: 404,
            message: 'Percakapan tidak ditemukan.',
          });
        }

        if (
          existingConversation.language !== input.language
        ) {
          await updateConversationLanguageRowForUser(
            conversationId,
            input.userId,
            input.language,
            client
          );
        }

        effectiveLanguage = input.language;
      } else {
        conversationId =
          await createConversationForUser(
            input.language,
            input.userId,
            client,
            buildAutoConversationTitle(question)
          );
      }

      const attachments =
        buildAttachments(input.files);

      const userMessageId =
        await createUserMessage(
          {
            conversationId,
            content: question,
            attachments,
          },
          client
        );

      await touchConversation(
        conversationId,
        client
      );

      return {
        conversationId,
        userMessageId,
        language: effectiveLanguage,
      };
    }
  );
};

export const processChat = async (
  input: ProcessChatInput
): Promise<ProcessChatResult> => {
  const startedAt = Date.now();

  const question =
    normalizeQuestion(
      input.message,
      input.files
    );

  if (!question) {
    throw createValidationError(
      'Pesan tidak boleh kosong.'
    );
  }

  const {
    conversationId,
    userMessageId,
    language,
  } = await saveUserMessage(
    input,
    question
  );

  const conversationHistory =
    await getConversationHistory(
      conversationId,
      userMessageId
    );

  const ragResult =
    await answerWithRag({
      question,
      language,
      conversationHistory,
    });

  const answer =
    ragResult.answer;

  const sources =
    mapSources(ragResult.sources);

  return withTransaction<ProcessChatResult>(
    async (
      client: PoolClient
    ): Promise<ProcessChatResult> => {
      const assistantRow =
        await createAssistantMessage(
          {
            conversationId,
            content: answer,
            confidence: ragResult.confidence,
            modelName: ragResult.model,
          },
          client
        );

      await createQueryLog(
        {
          requestId: randomUUID(),
          conversationId,
          userId: input.userId,
          userMessageId,
          assistantMessageId: assistantRow.id,
          question,
          answer,
          language,
          status: 'ANSWERED',
          confidenceScore: ragResult.confidence,
          responseTimeMs: Date.now() - startedAt,
          modelName: ragResult.model,
          retrievedDocuments: sources,
        },
        client
      );

      await touchConversation(
        conversationId,
        client
      );

      return {
        conversationId,
        messageId:
          assistantRow.id,
        answer,
        confidence:
          ragResult.confidence,
        sources,
        createdAt:
          assistantRow.created_at.toISOString(),
        language,
      };
    }
  );
};

export const listConversations =
  async (userId: string) => {
    const rows =
      await listConversationRowsByUser(userId);

    return rows.map((row) => ({
      id: row.id,
      title: row.title,
      language: row.language,
      pinned: row.is_pinned,
      createdAt:
        row.created_at.toISOString(),
      updatedAt:
        row.updated_at.toISOString(),
    }));
  };

export const findConversationById =
  async (
    conversationId: string,
    userId: string
  ) => {
    const row =
      await findConversationRowByIdAndUser(
        conversationId,
        userId
      );

    if (!row) {
      return null;
    }

    const messages =
      await listConversationMessages(
        conversationId
      );

    return {
      id: row.id,
      title: row.title,
      language: row.language,
      pinned: row.is_pinned,
      createdAt:
        row.created_at.toISOString(),
      updatedAt:
        row.updated_at.toISOString(),
      messages: messages.map(
        (message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          attachments:
            message.attachments,
          confidence:
            message.confidence ??
            undefined,
          time:
            message.created_at.toISOString(),
        })
      ),
    };
  };

export const updateConversationTitle =
  async (
    conversationId: string,
    userId: string,
    title: string
  ) => {
    const row =
      await updateConversationTitleRowForUser(
        conversationId,
        userId,
        title
      );

    if (!row) {
      return null;
    }

    return {
      id: row.id,
      title: row.title,
      language: row.language,
      pinned: row.is_pinned,
      createdAt:
        row.created_at.toISOString(),
      updatedAt:
        row.updated_at.toISOString(),
    };
  };

export const removeConversation =
  async (
    conversationId: string,
    userId: string
  ): Promise<boolean> => {
    return deleteConversationByIdForUser(
      conversationId,
      userId
    );
  };
