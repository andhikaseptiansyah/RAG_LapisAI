import {
  apiRequest,
  buildQueryString,
} from './api';

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

export interface TrainedDocument {
  id: string;
  filename: string;
  type: DocumentType;
  size: string;
  chunks: number;
  indexedAt: string;
  vectorStatus: VectorStatus;
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

export interface DocumentListParams {
  search?: string;
  page?: number;
  limit?: number;
  status?: IndexedStatus;
  type?: DocumentType;
}

export interface DocumentListResponse {
  documents: RepositoryDocument[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface UploadDocumentsResponse {
  message: string;
  uploadItems: UploadItem[];
}

export interface DocumentConflictResponse {
  duplicateFilenames: string[];
}

export interface IndexDocumentsPayload {
  documentIds?: string[];
}

export interface IndexDocumentsResponse {
  message: string;
  uploadItems: UploadItem[];
}

export interface TrainedDocumentsResponse {
  documents: TrainedDocument[];
  total: number;
}

export const getDocuments = async (
  params: DocumentListParams = {},
  signal?: AbortSignal
): Promise<DocumentListResponse> => {
  const query = buildQueryString({
    search: params.search,
    page: params.page,
    limit: params.limit,
    status: params.status,
    type: params.type,
  });

  return apiRequest<DocumentListResponse>(
    `/api/admin/documents${query}`,
    {
      method: 'GET',
      signal,
    }
  );
};

export const getUploadQueue = async (
  signal?: AbortSignal
): Promise<UploadItem[]> => {
  return apiRequest<UploadItem[]>(
    '/api/admin/documents/uploads',
    {
      method: 'GET',
      signal,
    }
  );
};

export const getTrainedDocuments = async (
  signal?: AbortSignal
): Promise<TrainedDocumentsResponse> => {
  return apiRequest<TrainedDocumentsResponse>(
    '/api/admin/documents/trained',
    {
      method: 'GET',
      signal,
    }
  );
};

export const checkDocumentConflicts = async (
  filenames: string[],
  signal?: AbortSignal
): Promise<DocumentConflictResponse> => {
  return apiRequest<
    DocumentConflictResponse,
    { filenames: string[] }
  >('/api/admin/documents/conflicts', {
    method: 'POST',
    body: { filenames },
    signal,
  });
};

export const uploadDocuments = async (
  files: File[],
  replaceFilenames: string[] = [],
  signal?: AbortSignal
): Promise<UploadDocumentsResponse> => {
  if (files.length === 0) {
    throw new Error('No files were selected.');
  }

  const formData = new FormData();

  files.forEach((file) => {
    formData.append('files', file);
  });

  formData.append(
    'replaceFilenamesJson',
    JSON.stringify(replaceFilenames)
  );

  return apiRequest<
    UploadDocumentsResponse,
    FormData
  >('/api/admin/documents', {
    method: 'POST',
    body: formData,
    signal,
  });
};

export const reindexDocuments = async (
  documentIds?: string[]
): Promise<IndexDocumentsResponse> => {
  return apiRequest<
    IndexDocumentsResponse,
    IndexDocumentsPayload
  >('/api/admin/documents/index', {
    method: 'POST',
    body: {
      documentIds,
    },
  });
};

export const getDocumentIndexingStatus = async (
  documentId: string,
  signal?: AbortSignal
): Promise<UploadItem> => {
  return apiRequest<UploadItem>(
    `/api/admin/documents/${encodeURIComponent(
      documentId
    )}/status`,
    {
      method: 'GET',
      signal,
    }
  );
};

export const reindexDocument = async (
  documentId: string
): Promise<UploadItem> => {
  return apiRequest<UploadItem>(
    `/api/admin/documents/${encodeURIComponent(
      documentId
    )}/reindex`,
    {
      method: 'POST',
    }
  );
};

export const deleteDocument = async (
  documentId: string
): Promise<void> => {
  await apiRequest<null>(
    `/api/admin/documents/${encodeURIComponent(
      documentId
    )}`,
    {
      method: 'DELETE',
    }
  );
};
