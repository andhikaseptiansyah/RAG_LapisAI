import type {
  PoolClient,
  QueryResult,
  QueryResultRow,
} from 'pg';

import { query } from '../config/database.js';

export type ConversationLanguage = 'ID' | 'EN';

export interface IdRow extends QueryResultRow {
  id: string;
}

export interface ConversationRow extends QueryResultRow {
  id: string;
  user_id: string | null;
  title: string;
  language: ConversationLanguage;
  is_pinned: boolean;
  created_at: Date;
  updated_at: Date;
}

const execute = async <T extends QueryResultRow>(
  sql: string,
  params: unknown[] = [],
  client?: PoolClient
): Promise<QueryResult<T>> => {
  if (client) {
    return client.query<T>(sql, params);
  }

  return query<T>(sql, params);
};

export const findConversationIdById = async (
  conversationId: string,
  client?: PoolClient
): Promise<string | null> => {
  const result = await execute<IdRow>(
    `
      select id
      from public.conversations
      where id = $1
    `,
    [conversationId],
    client
  );

  return result.rows[0]?.id ?? null;
};

export const createConversation = async (
  language: ConversationLanguage,
  client?: PoolClient
): Promise<string> => {
  const result = await execute<IdRow>(
    `
      insert into public.conversations (
        language
      )
      values ($1)
      returning id
    `,
    [language],
    client
  );

  const row = result.rows[0];

  if (!row) {
    throw new Error('Gagal membuat percakapan.');
  }

  return row.id;
};

export const createConversationForUser = async (
  language: ConversationLanguage,
  userId: string | null,
  client?: PoolClient,
  title?: string
): Promise<string> => {
  const normalizedTitle =
    typeof title === 'string' && title.trim()
      ? title.trim()
      : null;

  const result = await execute<IdRow>(
    `
      insert into public.conversations (
        language,
        user_id,
        title
      )
      values ($1, $2, $3)
      returning id
    `,
    [language, userId, normalizedTitle],
    client
  );

  const row = result.rows[0];

  if (!row) {
    throw new Error('Gagal membuat percakapan.');
  }

  return row.id;
};

export const touchConversation = async (
  conversationId: string,
  client?: PoolClient
): Promise<void> => {
  await execute(
    `
      update public.conversations
      set
        updated_at = now(),
        last_message_at = now()
      where id = $1
    `,
    [conversationId],
    client
  );
};

export const listConversationRows = async (): Promise<ConversationRow[]> => {
  const result = await execute<ConversationRow>(
    `
      select
        id,
        user_id,
        title,
        language,
        is_pinned,
        created_at,
        updated_at
      from public.conversations
      order by
        is_pinned desc,
        last_message_at desc
    `
  );

  return result.rows;
};

export const findConversationRowById = async (
  conversationId: string
): Promise<ConversationRow | null> => {
  const result = await execute<ConversationRow>(
    `
      select
        id,
        user_id,
        title,
        language,
        is_pinned,
        created_at,
        updated_at
      from public.conversations
      where id = $1
    `,
    [conversationId]
  );

  return result.rows[0] ?? null;
};

export const updateConversationTitleRow = async (
  conversationId: string,
  title: string
): Promise<ConversationRow | null> => {
  const result = await execute<ConversationRow>(
    `
      update public.conversations
      set
        title = $2,
        updated_at = now()
      where id = $1
      returning
        id,
        user_id,
        title,
        language,
        is_pinned,
        created_at,
        updated_at
    `,
    [conversationId, title]
  );

  return result.rows[0] ?? null;
};

export const deleteConversationById = async (
  conversationId: string
): Promise<boolean> => {
  const result = await execute<IdRow>(
    `
      delete from public.conversations
      where id = $1
      returning id
    `,
    [conversationId]
  );

  return (result.rowCount ?? 0) > 0;
};

export const findConversationIdByIdAndUser = async (
  conversationId: string,
  userId: string,
  client?: PoolClient
): Promise<string | null> => {
  const result = await execute<IdRow>(
    `
      select id
      from public.conversations
      where id = $1
        and user_id = $2
    `,
    [conversationId, userId],
    client
  );

  return result.rows[0]?.id ?? null;
};

export const listConversationRowsByUser = async (
  userId: string
): Promise<ConversationRow[]> => {
  const result = await execute<ConversationRow>(
    `
      select
        id,
        user_id,
        title,
        language,
        is_pinned,
        created_at,
        updated_at
      from public.conversations
      where user_id = $1
      order by
        is_pinned desc,
        last_message_at desc
    `,
    [userId]
  );

  return result.rows;
};

export const findConversationRowByIdAndUser = async (
  conversationId: string,
  userId: string,
  client?: PoolClient
): Promise<ConversationRow | null> => {
  const result = await execute<ConversationRow>(
    `
      select
        id,
        user_id,
        title,
        language,
        is_pinned,
        created_at,
        updated_at
      from public.conversations
      where id = $1
        and user_id = $2
    `,
    [conversationId, userId],
    client
  );

  return result.rows[0] ?? null;
};

export const updateConversationLanguageRowForUser = async (
  conversationId: string,
  userId: string,
  language: ConversationLanguage,
  client?: PoolClient
): Promise<ConversationRow | null> => {
  const result = await execute<ConversationRow>(
    `
      update public.conversations
      set
        language = $3::public.conversation_language,
        updated_at = now()
      where id = $1
        and user_id = $2
      returning
        id,
        user_id,
        title,
        language,
        is_pinned,
        created_at,
        updated_at
    `,
    [conversationId, userId, language],
    client
  );

  return result.rows[0] ?? null;
};

export const updateConversationTitleRowForUser = async (
  conversationId: string,
  userId: string,
  title: string
): Promise<ConversationRow | null> => {
  const result = await execute<ConversationRow>(
    `
      update public.conversations
      set
        title = $3,
        updated_at = now()
      where id = $1
        and user_id = $2
      returning
        id,
        user_id,
        title,
        language,
        is_pinned,
        created_at,
        updated_at
    `,
    [conversationId, userId, title]
  );

  return result.rows[0] ?? null;
};

export const deleteConversationByIdForUser = async (
  conversationId: string,
  userId: string
): Promise<boolean> => {
  const result = await execute<IdRow>(
    `
      delete from public.conversations
      where id = $1
        and user_id = $2
      returning id
    `,
    [conversationId, userId]
  );

  return (result.rowCount ?? 0) > 0;
};
