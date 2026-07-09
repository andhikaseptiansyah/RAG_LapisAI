import type {
  PoolClient,
  QueryResult,
  QueryResultRow,
} from 'pg';

import { query } from '../config/database.js';

export type QueryRange =
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'yearly';

export type QueryLogStatus =
  | 'ANSWERED'
  | 'NEED_REVIEW'
  | 'FAILED';

export interface QueryLogFilters {
  range: QueryRange;
  page: number;
  limit: number;
  status?: QueryLogStatus;
  search?: string;
}

export interface SourceRecord {
  documentId?: string | null;
  document_id?: string | null;
  chunkId?: string | null;
  chunk_id?: string | null;
  documentName?: string | null;
  document_name?: string | null;
  page?: string | number | null;
  pageNumber?: string | number | null;
  page_number?: string | number | null;
  chunkIndex?: string | number | null;
  chunk_index?: string | number | null;
  relevanceScore?: string | number | null;
  relevance_score?: string | number | null;
  score?: string | number | null;
  excerpt?: string | null;
  content?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface QueryLogRow extends QueryResultRow {
  query_id: string;
  user_name: string | null;
  user_question: string;
  timestamp: Date;
  retrieved_documents: SourceRecord[] | null;
  answer_generated: string | null;
  confidence_score: string | number | null;
  response_time_ms: string | number | null;
  status: QueryLogStatus;
}

export interface PerformanceRow extends QueryResultRow {
  total_queries: string;
  answered: string;
  not_found: string;
  need_review: string;
  errors: string;
  average_confidence: string | number | null;
  average_response_time: string | number | null;
}

interface CountRow extends QueryResultRow {
  total: string;
}

interface IdRow extends QueryResultRow {
  id: string;
}

export interface CreateQueryLogInput {
  requestId: string;
  conversationId: string | null;
  userId?: string | null;
  userMessageId: string | null;
  assistantMessageId: string | null;
  question: string;
  answer: string;
  language: 'ID' | 'EN';
  status: QueryLogStatus;
  confidenceScore: number;
  responseTimeMs: number;
  modelName: string;
  promptTokens?: number | null;
  completionTokens?: number | null;
  totalTokens?: number | null;
  errorMessage?: string | null;
  metadata?: Record<string, unknown>;
  retrievedDocuments?: SourceRecord[];
}

export interface QueryLogListRowsResult {
  rows: QueryLogRow[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
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

const intervalForRange = (
  range: QueryRange
): string => {
  const map: Record<QueryRange, string> = {
    daily: '1 day',
    weekly: '7 days',
    monthly: '1 month',
    yearly: '1 year',
  };

  return map[range];
};

const buildWhereClause = (
  filters: QueryLogFilters
) => {
  const conditions = [
    `created_at >= now() - $1::interval`,
  ];

  const values: unknown[] = [
    intervalForRange(filters.range),
  ];

  if (filters.status) {
    values.push(filters.status);
    conditions.push(
      `status = $${values.length}::public.query_status`
    );
  }

  if (filters.search) {
    values.push(`%${filters.search}%`);
    conditions.push(
      `(
        question ilike $${values.length}
        or answer ilike $${values.length}
        or user_display_name ilike $${values.length}
        or user_email ilike $${values.length}
      )`
    );
  }

  return {
    whereClause: `where ${conditions.join(' and ')}`,
    values,
  };
};

const toNumberOrNull = (
  value: string | number | null | undefined
): number | null => {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const normalizeSource = (source: SourceRecord) => {
  const documentId =
    source.documentId ??
    source.document_id ??
    null;

  const chunkId =
    source.chunkId ??
    source.chunk_id ??
    null;

  const documentName =
    source.documentName ??
    source.document_name ??
    'Dokumen tanpa nama';

  const pageNumber = toNumberOrNull(
    source.pageNumber ??
      source.page_number ??
      source.page
  );

  const chunkIndex = toNumberOrNull(
    source.chunkIndex ??
      source.chunk_index
  );

  const relevanceScore =
    toNumberOrNull(
      source.relevanceScore ??
        source.relevance_score ??
        source.score
    ) ?? 0;

  const excerpt =
    source.excerpt ??
    source.content ??
    null;

  return {
    documentId,
    chunkId,
    documentName,
    pageNumber,
    chunkIndex,
    relevanceScore: Math.max(
      0,
      Math.min(1, relevanceScore)
    ),
    excerpt,
    metadata: source.metadata ?? {},
  };
};

export const createQuerySources = async (
  queryLogId: string,
  sources: SourceRecord[],
  client?: PoolClient
): Promise<void> => {
  for (const [index, source] of sources.entries()) {
    const normalized = normalizeSource(source);

    await execute(
      `
        insert into public.query_sources (
          query_log_id,
          document_id,
          chunk_id,
          document_name,
          page_number,
          chunk_index,
          relevance_score,
          rank_position,
          excerpt,
          metadata
        )
        values (
          $1,
          $2,
          $3,
          $4,
          $5,
          $6,
          $7,
          $8,
          $9,
          $10::jsonb
        )
        on conflict (query_log_id, rank_position)
        do update set
          document_id = excluded.document_id,
          chunk_id = excluded.chunk_id,
          document_name = excluded.document_name,
          page_number = excluded.page_number,
          chunk_index = excluded.chunk_index,
          relevance_score = excluded.relevance_score,
          excerpt = excluded.excerpt,
          metadata = excluded.metadata
      `,
      [
        queryLogId,
        normalized.documentId,
        normalized.chunkId,
        normalized.documentName,
        normalized.pageNumber,
        normalized.chunkIndex,
        normalized.relevanceScore,
        index + 1,
        normalized.excerpt,
        JSON.stringify(normalized.metadata),
      ],
      client
    );
  }
};

export const createQueryLog = async (
  input: CreateQueryLogInput,
  client?: PoolClient
): Promise<string> => {
  const result = await execute<IdRow>(
    `
      insert into public.query_logs (
        request_id,
        conversation_id,
        user_id,
        user_message_id,
        assistant_message_id,
        question,
        answer,
        language,
        status,
        confidence_score,
        response_time_ms,
        model_name,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        error_message,
        metadata
      )
      values (
        $1,
        $2,
        $3,
        $4,
        $5,
        $6,
        $7,
        $8::public.conversation_language,
        $9::public.query_status,
        $10,
        $11,
        $12,
        $13,
        $14,
        $15,
        $16,
        $17::jsonb
      )
      returning id
    `,
    [
      input.requestId,
      input.conversationId,
      input.userId ?? null,
      input.userMessageId,
      input.assistantMessageId,
      input.question,
      input.answer,
      input.language,
      input.status,
      input.confidenceScore,
      input.responseTimeMs,
      input.modelName,
      input.promptTokens ?? null,
      input.completionTokens ?? null,
      input.totalTokens ?? null,
      input.errorMessage ?? null,
      JSON.stringify(input.metadata ?? {}),
    ],
    client
  );

  const queryLogId = result.rows[0]?.id;

  if (!queryLogId) {
    throw new Error('Gagal menyimpan query log.');
  }

  if (input.retrievedDocuments?.length) {
    await createQuerySources(
      queryLogId,
      input.retrievedDocuments,
      client
    );
  }

  return queryLogId;
};

export const listQueryLogRows = async (
  filters: QueryLogFilters
): Promise<QueryLogListRowsResult> => {
  const { whereClause, values } =
    buildWhereClause(filters);

  const countResult = await execute<CountRow>(
    `
      select count(*)::text as total
      from public.query_log_detail_view
      ${whereClause}
    `,
    values
  );

  const offset =
    (filters.page - 1) * filters.limit;
  const limitPosition = values.length + 1;
  const offsetPosition = values.length + 2;

  const result = await execute<QueryLogRow>(
    `
      select
        id as query_id,
        coalesce(user_display_name, user_email, 'Anonymous') as user_name,
        question as user_question,
        created_at as timestamp,
        retrieved_documents,
        answer as answer_generated,
        confidence_score,
        response_time_ms,
        status
      from public.query_log_detail_view
      ${whereClause}
      order by created_at desc
      limit $${limitPosition}
      offset $${offsetPosition}
    `,
    [
      ...values,
      filters.limit,
      offset,
    ]
  );

  const total = Number(
    countResult.rows[0]?.total ?? 0
  );

  return {
    rows: result.rows,
    total,
    page: filters.page,
    limit: filters.limit,
    totalPages: Math.max(
      Math.ceil(total / filters.limit),
      1
    ),
  };
};

export const loadQueryLogPerformanceRow = async (
  filters: QueryLogFilters
): Promise<PerformanceRow | null> => {
  const { whereClause, values } =
    buildWhereClause(filters);

  const result = await execute<PerformanceRow>(
    `
      select
        count(*)::text as total_queries,
        count(*) filter (
          where status = 'ANSWERED'::public.query_status
        )::text as answered,
        '0'::text as not_found,
        count(*) filter (
          where status = 'NEED_REVIEW'::public.query_status
        )::text as need_review,
        count(*) filter (
          where status = 'FAILED'::public.query_status
        )::text as errors,
        coalesce(
          avg(confidence_score),
          0
        ) as average_confidence,
        coalesce(
          avg(response_time_ms),
          0
        ) as average_response_time
      from public.query_log_detail_view
      ${whereClause}
    `,
    values
  );

  return result.rows[0] ?? null;
};

export const findQueryLogRowById = async (
  queryId: string
): Promise<QueryLogRow | null> => {
  const result = await execute<QueryLogRow>(
    `
      select
        id as query_id,
        coalesce(user_display_name, user_email, 'Anonymous') as user_name,
        question as user_question,
        created_at as timestamp,
        retrieved_documents,
        answer as answer_generated,
        confidence_score,
        response_time_ms,
        status
      from public.query_log_detail_view
      where id = $1
    `,
    [queryId]
  );

  return result.rows[0] ?? null;
};

export const deleteQueryLogById = async (
  queryId: string
): Promise<boolean> => {
  const result = await execute<IdRow>(
    `
      delete from public.query_logs
      where id = $1
      returning id
    `,
    [queryId]
  );

  return (result.rowCount ?? 0) > 0;
};
