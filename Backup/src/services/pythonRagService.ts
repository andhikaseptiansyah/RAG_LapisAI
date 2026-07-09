import { env } from '../config/env.js';

export interface PythonIndexInput {
  documentId: string;
  filePath: string;
  filename: string;
  metadata?: Record<string, unknown>;
}

export interface PythonIndexResult {
  status: string;
  document_id?: string;
  documentId?: string;
  filename: string;
  chunks: number;
  embedding_provider?: string;
  embedding_model?: string;
}

export interface PythonRetrievedChunk {
  chunkId: string;
  documentId: string;
  documentName: string;
  page: string;
  content: string;
  score: number;
  semanticScore?: number;
  keywordScore?: number;
  metadata?: Record<string, unknown>;
}

export interface PythonRetrieveResult {
  chunks: PythonRetrievedChunk[];
}

const trimTrailingSlash = (value: string): string => {
  return value.replace(/\/+$/, '');
};

const buildUrl = (path: string): string => {
  return `${trimTrailingSlash(env.RAG_PYTHON_URL)}${path}`;
};

const requestPythonRag = async <T>(
  path: string,
  payload?: Record<string, unknown>
): Promise<T> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    env.RAG_PYTHON_TIMEOUT_MS
  );

  try {
    const response = await fetch(buildUrl(path), {
      method: payload ? 'POST' : 'GET',
      headers: payload
        ? {
            'Content-Type': 'application/json',
          }
        : undefined,
      body: payload
        ? JSON.stringify(payload)
        : undefined,
      signal: controller.signal,
    });

    const text = await response.text();
    const data = text
      ? JSON.parse(text) as unknown
      : null;

    if (!response.ok) {
      const detail =
        typeof data === 'object' &&
        data !== null &&
        'detail' in data
          ? String((data as { detail: unknown }).detail)
          : response.statusText;

      throw new Error(
        `Python RAG service error (${response.status}): ${detail}`
      );
    }

    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error(
        `Python RAG service timeout setelah ${env.RAG_PYTHON_TIMEOUT_MS}ms.`
      );
    }

    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
};

export const checkPythonRagHealth = async (): Promise<boolean> => {
  try {
    await requestPythonRag('/health');
    return true;
  } catch {
    return false;
  }
};

export const indexDocumentWithPython = async (
  input: PythonIndexInput
): Promise<PythonIndexResult> => {
  return requestPythonRag<PythonIndexResult>('/index', {
    documentId: input.documentId,
    filePath: input.filePath,
    filename: input.filename,
    metadata: input.metadata ?? {},
  });
};

export const retrieveChunksWithPython = async (
  query: string,
  topK: number,
  minScore: number
): Promise<PythonRetrievedChunk[]> => {
  const result = await requestPythonRag<PythonRetrieveResult>('/retrieve', {
    query,
    topK,
    minScore,
  });

  return result.chunks ?? [];
};
