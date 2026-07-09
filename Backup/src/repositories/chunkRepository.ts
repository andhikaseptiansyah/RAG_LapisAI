import type {
  PoolClient,
  QueryResult,
  QueryResultRow,
} from 'pg';

import { query } from '../config/database.js';

export interface RetrievedChunkRow extends QueryResultRow {
  chunk_id: string;
  document_id: string;
  document_name: string;
  chunk_index: string | number;
  page_number: string | number | null;
  content: string;
  score: string | number | null;
  metadata: Record<string, unknown> | null;
}

export interface CreateChunkInput {
  documentId: string;
  chunkIndex: number;
  content: string;
  embeddingVector: string;
  pageNumber?: number | null;
  startChar?: number | null;
  endChar?: number | null;
  tokenCount?: number | null;
  metadata?: Record<string, unknown>;
}

interface CountRow extends QueryResultRow {
  total: string;
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

export const retrieveRelevantChunkRows = async (
  vector: string,
  topK: number,
  similarityThreshold = 0
): Promise<RetrievedChunkRow[]> => {
  const result = await execute<RetrievedChunkRow>(
    `
      select
        dc.id as chunk_id,
        d.id as document_id,
        d.filename as document_name,
        dc.chunk_index,
        dc.page_number,
        dc.content,
        1 - (dc.embedding <=> $1::vector) as score,
        dc.metadata
      from public.document_chunks dc
      join public.documents d
        on d.id = dc.document_id
      where
        dc.embedding is not null
        and d.status = 'indexed'::public.document_status
        and d.vector_status = 'completed'::public.vector_status
        and (1 - (dc.embedding <=> $1::vector)) >= $3
      order by dc.embedding <=> $1::vector
      limit greatest($2::integer, 1)
    `,
    [vector, topK, similarityThreshold]
  );

  return result.rows;
};

export const deleteChunksByDocumentId = async (
  documentId: string,
  client?: PoolClient
): Promise<void> => {
  await execute(
    `
      delete from public.document_chunks
      where document_id = $1
    `,
    [documentId],
    client
  );
};

export const createDocumentChunk = async (
  input: CreateChunkInput,
  client?: PoolClient
): Promise<void> => {
  await execute(
    `
      insert into public.document_chunks (
        document_id,
        chunk_index,
        content,
        embedding,
        page_number,
        start_char,
        end_char,
        token_count,
        metadata
      )
      values (
        $1,
        $2,
        $3,
        $4::vector,
        $5,
        $6,
        $7,
        $8,
        $9::jsonb
      )
      on conflict (document_id, chunk_index)
      do update set
        content = excluded.content,
        embedding = excluded.embedding,
        page_number = excluded.page_number,
        start_char = excluded.start_char,
        end_char = excluded.end_char,
        token_count = excluded.token_count,
        metadata = excluded.metadata
    `,
    [
      input.documentId,
      input.chunkIndex,
      input.content,
      input.embeddingVector,
      input.pageNumber ?? null,
      input.startChar ?? null,
      input.endChar ?? null,
      input.tokenCount ?? null,
      JSON.stringify(input.metadata ?? {}),
    ],
    client
  );
};

export const createDocumentChunks = async (
  chunks: CreateChunkInput[],
  client?: PoolClient
): Promise<void> => {
  if (chunks.length === 0) {
    return;
  }

  for (const chunk of chunks) {
    await createDocumentChunk(chunk, client);
  }
};

export const countChunksByDocumentId = async (
  documentId: string,
  client?: PoolClient
): Promise<number> => {
  const result = await execute<CountRow>(
    `
      select count(*)::text as total
      from public.document_chunks
      where document_id = $1
    `,
    [documentId],
    client
  );

  return Number(result.rows[0]?.total ?? 0);
};
