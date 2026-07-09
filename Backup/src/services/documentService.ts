import fs from 'node:fs';
import path from 'node:path';

import {
  createDocumentRow,
  deleteDocumentById,
  findDocumentRowById,
  listDocumentRows,
  listTrainedDocumentRows,
  listUploadQueueRows,
  markDocumentForReindexing,
  markDocumentsQueuedForIndexing,
  markDocumentFailed,
  markDocumentIndexed,
  updateDocumentIndexingProgress,
  type DocumentRow,
} from '../repositories/documentRepository.js';

import {
  indexDocumentWithPython,
} from './pythonRagService.js';

export type DocumentType =
  | 'PDF'
  | 'DOCX'
  | 'TXT';

export type UploadStatus =
  | 'Ready'
  | 'Parsing'
  | 'Chunking'
  | 'Embedding'
  | 'Indexed'
  | 'Rejected'
  | 'Failed';

export type IndexedStatus =
  | 'Indexed'
  | 'Re-indexed'
  | 'Pending';

export type VectorStatus =
  | 'Pending'
  | 'Active'
  | 'Removed';

export interface UploadedDocumentLike {
  originalname: string;
  mimetype: string;
  size: number;
  filename?: string;
  path?: string;
  buffer?: Buffer;
}

export interface ListDocumentsInput {
  search?: string;
  page: number;
  limit: number;
  status?: IndexedStatus;
  type?: DocumentType;
}

export interface UploadItem {
  id: string;
  filename: string;
  type: DocumentType;
  size: string;
  sizeBytes: number;
  uploadedAt: string;
  status: UploadStatus;
  progress: number;
  chunks: number;
  note: string;
}

export interface RepositoryDocument {
  id: string;
  filename: string;
  type: DocumentType;
  size: string;
  uploadDate: string;
  chunks: number;
  indexedStatus: IndexedStatus;
}

export interface TrainedDocument {
  id: string;
  filename: string;
  type: DocumentType;
  size: string;
  chunks: number;
  indexedAt: string;
  vectorStatus: VectorStatus;
}

const formatFileSize = (
  value: string | number
): string => {
  const bytes = Number(value);

  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B';
  }

  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  const size = bytes / 1024 ** index;

  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
};

const toDocumentType = (
  extension: string
): DocumentType => {
  const normalized = extension.toUpperCase();

  if (normalized === 'DOCX') return 'DOCX';
  if (normalized === 'TXT') return 'TXT';
  return 'PDF';
};

const toUploadStatus = (
  status: DocumentRow['status']
): UploadStatus => {
  const map: Record<
    DocumentRow['status'],
    UploadStatus
  > = {
    ready: 'Ready',
    processing: 'Chunking',
    indexed: 'Indexed',
    failed: 'Failed',
    archived: 'Rejected',
  };

  return map[status];
};

const toVectorStatus = (
  status: DocumentRow['vector_status']
): VectorStatus => {
  if (status === 'completed') return 'Active';
  if (status === 'failed') return 'Removed';
  return 'Pending';
};

const toUploadItem = (
  row: DocumentRow
): UploadItem => ({
  id: row.id,
  filename: row.filename,
  type: toDocumentType(row.file_extension),
  size: formatFileSize(row.file_size_bytes),
  sizeBytes: Number(row.file_size_bytes),
  uploadedAt: row.created_at.toISOString(),
  status: toUploadStatus(row.status),
  progress: row.indexing_progress,
  chunks: row.total_chunks,
  note: row.note,
});

const toRepositoryDocument = (
  row: DocumentRow
): RepositoryDocument => ({
  id: row.id,
  filename: row.filename,
  type: toDocumentType(row.file_extension),
  size: formatFileSize(row.file_size_bytes),
  uploadDate: row.created_at.toISOString(),
  chunks: row.total_chunks,
  indexedStatus:
    row.status === 'indexed'
      ? 'Indexed'
      : 'Pending',
});

export const listDocuments = async (
  input: ListDocumentsInput
) => {
  const result = await listDocumentRows({
    search: input.search,
    page: input.page,
    limit: input.limit,
    status: input.status,
    type: input.type,
  });

  return {
    documents: result.rows.map(toRepositoryDocument),
    total: result.total,
    page: input.page,
    limit: input.limit,
    totalPages: Math.max(
      Math.ceil(result.total / input.limit),
      1
    ),
  };
};

export const listUploadQueue = async () => {
  const rows = await listUploadQueueRows();

  return rows.map(toUploadItem);
};

export const listTrainedDocuments = async () => {
  const rows = await listTrainedDocumentRows();

  const documents: TrainedDocument[] =
    rows.map((row: DocumentRow) => ({
      id: row.id,
      filename: row.filename,
      type: toDocumentType(row.file_extension),
      size: formatFileSize(row.file_size_bytes),
      chunks: row.total_chunks,
      indexedAt: (
        row.indexed_at ?? row.created_at
      ).toISOString(),
      vectorStatus: toVectorStatus(
        row.vector_status
      ),
    }));

  return {
    documents,
    total: documents.length,
  };
};

export const uploadDocuments = async (
  files: UploadedDocumentLike[]
) => {
  const uploadItems: UploadItem[] = [];

  for (const file of files) {
    const extension =
      file.originalname
        .split('.')
        .pop()
        ?.toLowerCase() ?? 'txt';

    const row = await createDocumentRow({
      filename: file.filename ?? file.originalname,
      originalName: file.originalname,
      storagePath: file.path ?? file.filename ?? null,
      mimeType: file.mimetype,
      fileExtension: extension,
      fileSizeBytes: file.size,
    });

    uploadItems.push(toUploadItem(row));
  }

  return {
    message: 'Dokumen berhasil diunggah.',
    uploadItems,
  };
};

const resolveDocumentPath = (
  row: DocumentRow
): string => {
  if (!row.storage_path) {
    throw new Error(
      `Lokasi file untuk ${row.filename} tidak ditemukan.`
    );
  }

  const resolvedPath = path.isAbsolute(row.storage_path)
    ? row.storage_path
    : path.resolve(process.cwd(), row.storage_path);

  if (!fs.existsSync(resolvedPath)) {
    throw new Error(
      `File fisik tidak ditemukan di ${resolvedPath}.`
    );
  }

  return resolvedPath;
};

const runPythonIndexingPipeline = async (
  row: DocumentRow
): Promise<DocumentRow> => {
  try {
    await updateDocumentIndexingProgress(
      row.id,
      15,
      'Python pipeline: parsing dokumen.'
    );

    const filePath = resolveDocumentPath(row);

    await updateDocumentIndexingProgress(
      row.id,
      35,
      'Python pipeline: chunking dan ekstraksi teks.'
    );

    const result = await indexDocumentWithPython({
      documentId: row.id,
      filePath,
      filename: row.original_name || row.filename,
      metadata: {
        mimeType: row.mime_type,
        fileExtension: row.file_extension,
      },
    });

    await updateDocumentIndexingProgress(
      row.id,
      85,
      `Python pipeline: embedding selesai (${result.chunks} chunks).`
    );

    const indexedRow = await markDocumentIndexed(
      row.id,
      result.chunks
    );

    if (!indexedRow) {
      throw new Error(
        `Gagal memperbarui status indexing untuk ${row.filename}.`
      );
    }

    return indexedRow;
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : 'Python pipeline gagal memproses dokumen.';

    const failedRow = await markDocumentFailed(
      row.id,
      message
    );

    if (failedRow) {
      return failedRow;
    }

    throw error;
  }
};

export const startDocumentIndexing = async (
  documentIds?: string[]
) => {
  const rows =
    await markDocumentsQueuedForIndexing(
      documentIds
    );

  const processedRows: DocumentRow[] = [];

  for (const row of rows) {
    const processedRow =
      await runPythonIndexingPipeline(row);

    processedRows.push(processedRow);
  }

  return {
    message:
      processedRows.length > 0
        ? 'Python RAG pipeline selesai memproses dokumen.'
        : 'Tidak ada dokumen baru yang perlu di-index.',
    uploadItems: processedRows.map(toUploadItem),
  };
};

export const getDocumentIndexingStatus = async (
  documentId: string
): Promise<UploadItem | null> => {
  const row = await findDocumentRowById(
    documentId
  );

  return row ? toUploadItem(row) : null;
};

export const reindexDocument = async (
  documentId: string
): Promise<UploadItem | null> => {
  const row = await markDocumentForReindexing(
    documentId
  );

  if (!row) {
    return null;
  }

  const processedRow =
    await runPythonIndexingPipeline(row);

  return toUploadItem(processedRow);
};

export const removeDocument = async (
  documentId: string
): Promise<boolean> => {
  return deleteDocumentById(documentId);
};
