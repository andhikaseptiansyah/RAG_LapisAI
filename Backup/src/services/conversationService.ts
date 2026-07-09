import { query } from '../config/database.js';

export type ConversationSummary = {
  id: string;
  title: string;
  language: string;
  is_pinned: boolean;
  last_message_at: string;
  created_at: string;
  updated_at: string;
  last_message: string;
  last_user_message: string;
};

export type ConversationMessage = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  attachments: unknown[];
  confidence: number | null;
  model_name: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ConversationDetail = {
  conversation: ConversationSummary;
  messages: ConversationMessage[];
};

export type ConversationLanguage = 'ID' | 'EN';

export type UpdateUserConversationInput = {
  title?: string;
  is_pinned?: boolean;
  language?: ConversationLanguage;
};

const conversationSummarySelect = `
  SELECT
    c.id::text AS id,
    COALESCE(c.title, '') AS title,
    c.language::text AS language,
    c.is_pinned,
    c.last_message_at::text AS last_message_at,
    c.created_at::text AS created_at,
    c.updated_at::text AS updated_at,
    COALESCE(
      (
        SELECT m.content
        FROM public.messages m
        WHERE m.conversation_id = c.id
        ORDER BY m.created_at DESC
        LIMIT 1
      ),
      ''
    ) AS last_message,
    COALESCE(
      (
        SELECT m.content
        FROM public.messages m
        WHERE m.conversation_id = c.id
          AND m.role = 'user'::public.message_role
        ORDER BY m.created_at DESC
        LIMIT 1
      ),
      ''
    ) AS last_user_message
  FROM public.conversations c
`;

export const listUserConversations = async (
  userId: string
): Promise<ConversationSummary[]> => {
  const result =
    await query<ConversationSummary>(
      `
      ${conversationSummarySelect}
      WHERE c.user_id = $1::uuid
      ORDER BY
        c.is_pinned DESC,
        c.last_message_at DESC,
        c.created_at DESC
      LIMIT 50
      `,
      [userId]
    );

  return result.rows;
};

export const getUserConversationWithMessages =
  async (
    userId: string,
    conversationId: string
  ): Promise<ConversationDetail | null> => {
    const conversationResult =
      await query<ConversationSummary>(
        `
        ${conversationSummarySelect}
        WHERE c.id = $1::uuid
          AND c.user_id = $2::uuid
        LIMIT 1
        `,
        [conversationId, userId]
      );

    const conversation =
      conversationResult.rows[0];

    if (!conversation) {
      return null;
    }

    const messagesResult =
      await query<ConversationMessage>(
        `
        SELECT
          m.id::text AS id,
          m.conversation_id::text AS conversation_id,
          m.role::text AS role,
          m.content,
          COALESCE(m.attachments, '[]'::jsonb) AS attachments,
          m.confidence,
          m.model_name,
          COALESCE(m.metadata, '{}'::jsonb) AS metadata,
          m.created_at::text AS created_at
        FROM public.messages m
        WHERE m.conversation_id = $1::uuid
        ORDER BY m.created_at ASC
        `,
        [conversationId]
      );

    return {
      conversation,
      messages: messagesResult.rows,
    };
  };

export const updateUserConversation = async (
  userId: string,
  conversationId: string,
  input: UpdateUserConversationInput
): Promise<ConversationSummary | null> => {
  const hasTitle =
    typeof input.title === 'string';
  const normalizedTitle = hasTitle
    ? input.title?.trim()
    : undefined;

  const hasPinned =
    typeof input.is_pinned === 'boolean';

  const hasLanguage =
    input.language === 'ID' || input.language === 'EN';

  if (hasTitle && !normalizedTitle) {
    throw new Error('Judul percakapan wajib diisi.');
  }

  if (!hasTitle && !hasPinned && !hasLanguage) {
    throw new Error(
      'Tidak ada perubahan percakapan yang dikirim.'
    );
  }

  const result =
    await query<ConversationSummary>(
      `
      WITH updated AS (
        UPDATE public.conversations
        SET
          title = CASE
            WHEN $3::text IS NULL THEN title
            ELSE $3::text
          END,
          is_pinned = CASE
            WHEN $4::boolean IS NULL THEN is_pinned
            ELSE $4::boolean
          END,
          language = CASE
            WHEN $5::text IS NULL THEN language
            ELSE $5::public.conversation_language
          END,
          updated_at = now()
        WHERE id = $1::uuid
          AND user_id = $2::uuid
        RETURNING *
      )
      SELECT
        c.id::text AS id,
        COALESCE(c.title, '') AS title,
        c.language::text AS language,
        c.is_pinned,
        c.last_message_at::text AS last_message_at,
        c.created_at::text AS created_at,
        c.updated_at::text AS updated_at,
        COALESCE(
          (
            SELECT m.content
            FROM public.messages m
            WHERE m.conversation_id = c.id
            ORDER BY m.created_at DESC
            LIMIT 1
          ),
          ''
        ) AS last_message,
        COALESCE(
          (
            SELECT m.content
            FROM public.messages m
            WHERE m.conversation_id = c.id
              AND m.role = 'user'::public.message_role
            ORDER BY m.created_at DESC
            LIMIT 1
          ),
          ''
        ) AS last_user_message
      FROM updated c
      LIMIT 1
      `,
      [
        conversationId,
        userId,
        hasTitle ? normalizedTitle : null,
        hasPinned ? input.is_pinned : null,
        hasLanguage ? input.language : null,
      ]
    );

  return result.rows[0] ?? null;
};

export const removeUserConversation = async (
  userId: string,
  conversationId: string
): Promise<void> => {
  await query('BEGIN');

  try {
    const checkResult =
      await query<{ id: string }>(
        `
        SELECT id::text AS id
        FROM public.conversations
        WHERE id = $1::uuid
          AND user_id = $2::uuid
        LIMIT 1
        `,
        [conversationId, userId]
      );

    if (checkResult.rowCount === 0) {
      await query('ROLLBACK');
      return;
    }

    await query(
      `
      DELETE FROM public.query_sources
      WHERE query_log_id IN (
        SELECT id
        FROM public.query_logs
        WHERE conversation_id = $1::uuid
      )
      `,
      [conversationId]
    );

    await query(
      `
      DELETE FROM public.query_logs
      WHERE conversation_id = $1::uuid
      `,
      [conversationId]
    );

    await query(
      `
      DELETE FROM public.messages
      WHERE conversation_id = $1::uuid
      `,
      [conversationId]
    );

    await query(
      `
      DELETE FROM public.conversations
      WHERE id = $1::uuid
        AND user_id = $2::uuid
      `,
      [conversationId, userId]
    );

    await query('COMMIT');
  } catch (error) {
    await query('ROLLBACK');
    throw error;
  }
};
