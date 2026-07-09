import type {
  PoolClient,
  QueryResult,
  QueryResultRow,
} from 'pg';

import { query } from '../config/database.js';

export type MessageRole = 'user' | 'assistant' | 'system';

export interface IdRow extends QueryResultRow {
  id: string;
}

export interface CreatedAssistantMessageRow extends QueryResultRow {
  id: string;
  created_at: Date;
}

export interface MessageRow extends QueryResultRow {
  id: string;
  role: MessageRole;
  content: string;
  attachments: unknown[];
  confidence: number | null;
  created_at: Date;
}

export interface HistoryMessageRow extends QueryResultRow {
  role: MessageRole;
  content: string;
}

export interface CreateUserMessageInput {
  conversationId: string;
  content: string;
  attachments: unknown[];
}

export interface CreateAssistantMessageInput {
  conversationId: string;
  content: string;
  confidence: number;
  modelName: string;
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

export const createUserMessage = async (
  input: CreateUserMessageInput,
  client?: PoolClient
): Promise<string> => {
  const result = await execute<IdRow>(
    `
      insert into public.messages (
        conversation_id,
        role,
        content,
        attachments
      )
      values (
        $1,
        'user'::public.message_role,
        $2,
        $3::jsonb
      )
      returning id
    `,
    [
      input.conversationId,
      input.content,
      JSON.stringify(input.attachments ?? []),
    ],
    client
  );

  const row = result.rows[0];

  if (!row) {
    throw new Error('Gagal menyimpan pesan pengguna.');
  }

  return row.id;
};

export const createAssistantMessage = async (
  input: CreateAssistantMessageInput,
  client?: PoolClient
): Promise<CreatedAssistantMessageRow> => {
  const result = await execute<CreatedAssistantMessageRow>(
    `
      insert into public.messages (
        conversation_id,
        role,
        content,
        confidence,
        model_name
      )
      values (
        $1,
        'assistant'::public.message_role,
        $2,
        $3,
        $4
      )
      returning
        id,
        created_at
    `,
    [
      input.conversationId,
      input.content,
      input.confidence,
      input.modelName,
    ],
    client
  );

  const row = result.rows[0];

  if (!row) {
    throw new Error('Gagal menyimpan jawaban AI.');
  }

  return row;
};

export const listConversationMessages = async (
  conversationId: string
): Promise<MessageRow[]> => {
  const result = await execute<MessageRow>(
    `
      select
        id,
        role,
        content,
        attachments,
        confidence,
        created_at
      from public.messages
      where conversation_id = $1
      order by created_at asc
    `,
    [conversationId]
  );

  return result.rows;
};

export const listConversationHistoryRows = async (
  conversationId: string,
  excludedMessageId: string,
  limit = 8
): Promise<HistoryMessageRow[]> => {
  const result = await execute<HistoryMessageRow>(
    `
      select
        role,
        content
      from public.messages
      where conversation_id = $1
        and id <> $2
      order by created_at desc
      limit $3
    `,
    [conversationId, excludedMessageId, limit]
  );

  return result.rows;
};
