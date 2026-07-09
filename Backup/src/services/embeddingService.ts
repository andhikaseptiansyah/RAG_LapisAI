import { createHash } from 'node:crypto';

import { env } from '../config/env.js';

export interface CreateEmbeddingInput {
  text: string;
  model?: string;
}

export interface CreateEmbeddingResult {
  embedding: number[];
  model: string;
  provider: string;
}

interface OpenAiEmbeddingResponse {
  data?: Array<{
    embedding?: number[];
  }>;
  model?: string;
  error?: {
    message?: string;
  };
}

const AI_BASE_URL = (
  process.env.AI_BASE_URL ?? 'https://api.openai.com/v1'
).replace(/\/$/, '');

const DEFAULT_EMBEDDING_MODEL =
  env.EMBEDDING_MODEL ||
  process.env.OLLAMA_EMBEDDING_MODEL ||
  'text-embedding-3-small';

const EMBEDDING_PROVIDER =
  env.EMBEDDING_PROVIDER.toLowerCase();

const FALLBACK_DIMENSION = Number(
  process.env.FALLBACK_EMBEDDING_DIMENSION ?? 384
);

const DEFAULT_TIMEOUT_MS = Number(
  process.env.AI_TIMEOUT_MS ?? 60_000
);

const isLocalProvider = (baseUrl: string): boolean => {
  return (
    baseUrl.includes('localhost') ||
    baseUrl.includes('127.0.0.1') ||
    baseUrl.includes('host.docker.internal')
  );
};

const getProviderName = (): string => {
  if (AI_BASE_URL.includes('openai.com')) return 'openai';
  if (isLocalProvider(AI_BASE_URL)) return 'local-openai-compatible';
  return 'openai-compatible';
};

const buildHeaders = (): Record<string, string> => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (env.AI_API_KEY) {
    headers.Authorization = `Bearer ${env.AI_API_KEY}`;
  }

  return headers;
};

const normalizeText = (text: string): string => {
  return text.replace(/\s+/g, ' ').trim();
};

const normalizeVector = (vector: number[]): number[] => {
  const magnitude = Math.sqrt(
    vector.reduce((sum, value) => sum + value * value, 0)
  );

  if (magnitude === 0) return vector;

  return vector.map((value) => value / magnitude);
};

const createFallbackEmbedding = (text: string): number[] => {
  const vector = Array.from({ length: FALLBACK_DIMENSION }, () => 0);
  const tokens = normalizeText(text)
    .toLowerCase()
    .split(/[^a-z0-9]+/i)
    .filter(Boolean);

  for (const token of tokens) {
    const hash = createHash('sha256').update(token).digest();

    for (let i = 0; i < hash.length; i += 2) {
      const index = hash[i] % FALLBACK_DIMENSION;
      const sign = hash[i + 1] % 2 === 0 ? 1 : -1;
      vector[index] += sign;
    }
  }

  return normalizeVector(vector);
};

export const createEmbedding = async (
  input: CreateEmbeddingInput
): Promise<CreateEmbeddingResult> => {
  const text = normalizeText(input.text);
  const model = input.model ?? DEFAULT_EMBEDDING_MODEL;

  if (!text) {
    throw new Error('Teks embedding tidak boleh kosong.');
  }

  const shouldUseFallbackEmbedding =
    EMBEDDING_PROVIDER === 'fallback' ||
    model === 'fallback-hash-embedding';

  if (shouldUseFallbackEmbedding) {
    return {
      embedding: createFallbackEmbedding(text),
      model: 'fallback-hash-embedding',
      provider: 'local-fallback',
    };
  }

  if (!env.AI_API_KEY && !isLocalProvider(AI_BASE_URL)) {
    return {
      embedding: createFallbackEmbedding(text),
      model: 'fallback-hash-embedding',
      provider: 'local-fallback',
    };
  }

  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    DEFAULT_TIMEOUT_MS
  );

  try {
    const response = await fetch(`${AI_BASE_URL}/embeddings`, {
      method: 'POST',
      headers: buildHeaders(),
      signal: controller.signal,
      body: JSON.stringify({
        model,
        input: text,
      }),
    });

    const payload = (await response.json()) as OpenAiEmbeddingResponse;

    if (!response.ok) {
      throw new Error(
        payload.error?.message ??
          `Embedding service gagal dengan status ${response.status}.`
      );
    }

    const embedding = payload.data?.[0]?.embedding;

    if (!embedding || embedding.length === 0) {
      throw new Error('Embedding service tidak mengembalikan vector.');
    }

    return {
      embedding,
      model: payload.model ?? model,
      provider: getProviderName(),
    };
  } catch (error) {
    console.error('[EMBEDDING_SERVICE] createEmbedding failed:', error);

    return {
      embedding: createFallbackEmbedding(text),
      model: 'fallback-hash-embedding',
      provider: 'local-fallback',
    };
  } finally {
    clearTimeout(timeout);
  }
};

export const createEmbeddingsBatch = async (
  texts: string[]
): Promise<CreateEmbeddingResult[]> => {
  const results: CreateEmbeddingResult[] = [];

  for (const text of texts) {
    results.push(await createEmbedding({ text }));
  }

  return results;
};

export const toPgVector = (embedding: number[]): string => {
  if (!embedding.length) {
    throw new Error('Embedding vector tidak boleh kosong.');
  }

  return `[${embedding.join(',')}]`;
};