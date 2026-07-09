import type {
  PoolClient,
  QueryResult,
  QueryResultRow,
} from 'pg';

import { query } from '../config/database.js';

export type StoredDocumentStatus =
  | 'ready'
  | 'processing'
  | 'indexed'
  | 'failed'
  | 'archived';

export type StoredVectorStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

export type DocumentListStatus =
  | 'Indexed'
  | 'Re-indexed'
  | 'Pending';

export type DocumentListType =
  | 'PDF'
  | 'DOCX'
  | 'TXT';

export interface DocumentRow extends QueryResultRow {
  id: string;
  filename: string;
  original_name: string;
  file_extension: string;
  mime_type: string;
  storage_path: string | null;
  file_size_bytes: string | number;
  checksum_sha256: string | null;
  status: StoredDocumentStatus;
  vector_status: StoredVectorStatus;
  indexing_progress: number;
  total_chunks: number;
  note: string;
  indexed_at: Date | null;
  created_at: Date;
  updated_at: Date;
}

interface CountRow extends QueryResultRow {
  total: string;
}

interface IdRow extends QueryResultRow {
  id: string;
}

export interface ListDocumentRowsInput {
  search?: string;
  page: number;
  limit: number;
  status?: DocumentListStatus;
  type?: DocumentListType;
}

export interface ListDocumentRowsResult {
  rows: DocumentRow[];
  total: number;
}

export interface CreateDocumentInput {
  filename: string;
  originalName: string;
  storagePath: string | null;
  mimeType: string;
  fileExtension: string;
  fileSizeBytes: number;
  checksumSha256?: string | null;
  uploadedBy?: string | null;
  metadata?: Record<string, unknown>;
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

const buildListFilter = (
  input: Pick<
    ListDocumentRowsInput,
    'search' | 'status' | 'type'
  >
) => {
  const conditions: string[] = [];
  const values: unknown[] = [];

  if (input.search) {
    values.push(`%${input.search}%`);
    conditions.push(
      `(
        filename ilike $${values.length}
        or original_name ilike $${values.length}
      )`
    );
  }

  if (input.type) {
    values.push(input.type.toLowerCase());
    conditions.push(
      `lower(file_extension) = $${values.length}`
    );
  }

  if (
    input.status === 'Indexed' ||
    input.status === 'Re-indexed'
  ) {
    conditions.push(
      `status = 'indexed'::public.document_status`
    );
  }

  if (input.status === 'Pending') {
    conditions.push(
      `status <> 'indexed'::public.document_status`
    );
  }

  return {
    whereClause:
      conditions.length > 0
        ? `where ${conditions.join(' and ')}`
        : '',
    values,
  };
};

export const listDocumentRows = async (
  input: ListDocumentRowsInput
): Promise<ListDocumentRowsResult> => {
  const { whereClause, values } =
    buildListFilter(input);

  const countResult = await execute<CountRow>(
    `
      select count(*)::text as total
      from public.documents
      ${whereClause}
    `,
    values
  );

  const offset = (input.page - 1) * input.limit;
  const limitPosition = values.length + 1;
  const offsetPosition = values.length + 2;

  const result = await execute<DocumentRow>(
    `
      select *
      from public.documents
      ${whereClause}
      order by created_at desc
      limit $${limitPosition}
      offset $${offsetPosition}
    `,
    [
      ...values,
      input.limit,
      offset,
    ]
  );

  return {
    rows: result.rows,
    total: Number(
      countResult.rows[0]?.total ?? 0
    ),
  };
};

export const listUploadQueueRows = async (): Promise<DocumentRow[]> => {
  const result = await execute<DocumentRow>(
    `
      select *
      from public.documents
      where status <> 'indexed'::public.document_status
      order by created_at desc
    `
  );

  return result.rows;
};

export const listTrainedDocumentRows = async (): Promise<DocumentRow[]> => {
  const result = await execute<DocumentRow>(
    `
      select *
      from public.documents
      where status = 'indexed'::public.document_status
        and vector_status = 'completed'::public.vector_status
      order by indexed_at desc nulls last
    `
  );

  return result.rows;
};

export const createDocumentRow = async (
  input: CreateDocumentInput,
  client?: PoolClient
): Promise<DocumentRow> => {
  const result = await execute<DocumentRow>(
    `
      insert into public.documents (
        filename,
        original_name,
        storage_path,
        mime_type,
        file_extension,
        file_size_bytes,
        checksum_sha256,
        status,
        vector_status,
        indexing_progress,
        note,
        uploaded_by,
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
        'ready'::public.document_status,
        'pending'::public.vector_status,
        0,
        'Dokumen siap diproses.',
        $8,
        $9::jsonb
      )
      returning *
    `,
    [
      input.filename,
      input.originalName,
      input.storagePath,
      input.mimeType,
      input.fileExtension,
      input.fileSizeBytes,
      input.checksumSha256 ?? null,
      input.uploadedBy ?? null,
      JSON.stringify(input.metadata ?? {}),
    ],
    client
  );

  const row = result.rows[0];

  if (!row) {
    throw new Error(
      `Gagal menyimpan dokumen ${input.originalName}.`
    );
  }

  return row;
};

export const markDocumentsQueuedForIndexing = async (
  documentIds?: string[],
  client?: PoolClient
): Promise<DocumentRow[]> => {
  const values: unknown[] = [];
  let whereClause = `where status <> 'indexed'::public.document_status`;

  if (documentIds && documentIds.length > 0) {
    values.push(documentIds);
    whereClause += ` and id = any($1::uuid[])`;
  }

  const result = await execute<DocumentRow>(
    `
      update public.documents
      set
        status = 'processing'::public.document_status,
        vector_status = 'processing'::public.vector_status,
        indexing_progress = 0,
        note = 'Dokumen sedang diproses untuk indexing.',
        indexed_at = null,
        updated_at = now()
      ${whereClause}
      returning *
    `,
    values,
    client
  );

  return result.rows;
};

export const findDocumentRowById = async (
  documentId: string,
  client?: PoolClient
): Promise<DocumentRow | null> => {
  const result = await execute<DocumentRow>(
    `
      select *
      from public.documents
      where id = $1
    `,
    [documentId],
    client
  );

  return result.rows[0] ?? null;
};

export const markDocumentForReindexing = async (
  documentId: string,
  client?: PoolClient
): Promise<DocumentRow | null> => {
  const result = await execute<DocumentRow>(
    `
      update public.documents
      set
        status = 'processing'::public.document_status,
        vector_status = 'processing'::public.vector_status,
        indexing_progress = 0,
        total_chunks = 0,
        indexed_at = null,
        note = 'Dokumen sedang diproses ulang.',
        updated_at = now()
      where id = $1
      returning *
    `,
    [documentId],
    client
  );

  return result.rows[0] ?? null;
};

export const updateDocumentIndexingProgress = async (
  documentId: string,
  progress: number,
  note?: string,
  client?: PoolClient
): Promise<DocumentRow | null> => {
  const safeProgress = Math.max(
    0,
    Math.min(100, Math.round(progress))
  );

  const result = await execute<DocumentRow>(
    `
      update public.documents
      set
        status = 'processing'::public.document_status,
        vector_status = 'processing'::public.vector_status,
        indexing_progress = $2,
        note = coalesce($3, note),
        updated_at = now()
      where id = $1
      returning *
    `,
    [documentId, safeProgress, note ?? null],
    client
  );

  return result.rows[0] ?? null;
};

export const markDocumentIndexed = async (
  documentId: string,
  totalChunks: number,
  client?: PoolClient
): Promise<DocumentRow | null> => {
  const result = await execute<DocumentRow>(
    `
      update public.documents
      set
        status = 'indexed'::public.document_status,
        vector_status = 'completed'::public.vector_status,
        indexing_progress = 100,
        total_chunks = $2,
        indexed_at = now(),
        note = 'Dokumen berhasil di-index.',
        updated_at = now()
      where id = $1
      returning *
    `,
    [documentId, totalChunks],
    client
  );

  return result.rows[0] ?? null;
};

export const markDocumentFailed = async (
  documentId: string,
  errorMessage: string,
  client?: PoolClient
): Promise<DocumentRow | null> => {
  const result = await execute<DocumentRow>(
    `
      update public.documents
      set
        status = 'failed'::public.document_status,
        vector_status = 'failed'::public.vector_status,
        note = $2,
        updated_at = now()
      where id = $1
      returning *
    `,
    [documentId, errorMessage],
    client
  );

  return result.rows[0] ?? null;
};

export const deleteDocumentById = async (
  documentId: string,
  client?: PoolClient
): Promise<boolean> => {
  const result = await execute<IdRow>(
    `
      delete from public.documents
      where id = $1
      returning id
    `,
    [documentId],
    client
  );

  return (result.rowCount ?? 0) > 0;
};
